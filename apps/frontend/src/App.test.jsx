import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor, act } from '@testing-library/react';

jest.mock('./constants', () => ({
  API_BASE_URL: '',
  POLL_INTERVAL_MS: 10000,
}));

jest.mock('./timer', () => ({
  startPolling: jest.fn((cb) => {
    cb();
    return 1;
  }),
}));

import App from './App';

// Mock react-markdown to avoid ES module issues in tests
jest.mock('react-markdown', () => {
  return function ReactMarkdown({ children }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});

beforeEach(() => {
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.resetAllMocks();
});

function mockResponse(data) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
}

test('workflows display in succeeded, running and waiting states', async () => {
  fetch.mockImplementation((url) => {
    if (url === '/workflows') {
      return mockResponse([
        { id: '1', template: 'a', status: 'running' },
        { id: '2', template: 'b', status: 'needs_input' },
        { id: '3', template: 'c', status: 'succeeded' }
      ]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    return mockResponse({ id: '1', template: 'a', status: 'running', result: {} });
  });

  render(<App />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows'));
  await screen.findAllByRole('listitem');

  expect(document.querySelector('.state-running')).toBeTruthy();
  expect(document.querySelector('.state-needs-input')).toBeTruthy();
  expect(document.querySelector('.state-succeeded')).toBeTruthy();
});

test('user can start new workflow with selected template', async () => {
  fetch.mockImplementation((url, options) => {
    if (url === '/workflows' && !options) {
      return mockResponse([]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([
        { id: 'deepresearch', name: 'DeepResearch' },
        { id: 'example', name: 'Example' }
      ]);
    }
    if (url === '/workflows' && options?.method === 'POST') {
      const body = JSON.parse(options.body);
      expect(body.template_name).toBe('example');
      expect(body.query).toBe('my query');
      return mockResponse({ id: '10', template: 'example', status: 'running', result: {} });
    }
    if (url === '/workflows/10') {
      return mockResponse({ id: '10', template: 'example', status: 'running', result: {} });
    }
    return mockResponse({});
  });

  render(<App />);

  fireEvent.click(screen.getByText(/Start New Workflow/));

  await screen.findByText('Start');
  fireEvent.change(screen.getByPlaceholderText('Enter query...'), { target: { value: 'my query' } });
  fireEvent.change(screen.getByTestId('template-select'), { target: { value: 'example' } });
  fireEvent.click(screen.getByText('Start'));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows', expect.objectContaining({ method: 'POST' })));

  const runningElements = await screen.findAllByText('running');
  expect(runningElements.length).toBeGreaterThan(0);
});

test('canceling new workflow does not start it', async () => {
  fetch.mockImplementation((url, options) => {
    if (url === '/workflows' && !options) {
      return mockResponse([]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([{ id: 'deepresearch', name: 'DeepResearch' }]);
    }
    if (url === '/workflows' && options?.method === 'POST') {
      return mockResponse({});
    }
    return mockResponse({});
  });

  render(<App />);

  fireEvent.click(screen.getByText(/Start New Workflow/));
  await screen.findByText('Start');
  fireEvent.click(screen.getByText('Cancel'));

  await waitFor(() => {});

  expect(fetch).not.toHaveBeenCalledWith('/workflows', expect.objectContaining({ method: 'POST' }));
});

test('user can continue waiting workflow', async () => {
  fetch.mockImplementation((url, options) => {
    if (url === '/workflows' && !options) {
      return mockResponse([{ id: '5', template: 'deepresearch', status: 'needs_input' }]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    if (url === '/workflows/5') {
      return mockResponse({
        id: '5',
        template: 'deepresearch',
        status: 'needs_input',
        result: { __interrupt__: [{ value: { questions: ['clarify?'] } }] }
      });
    }
    if (url === '/workflows/5/continue') {
      return mockResponse({ id: '5', template: 'deepresearch', status: 'succeeded', result: { final_answer: 'done' } });
    }
    return mockResponse({});
  });

  render(<App />);

  await screen.findByText('needs_input');
  await screen.findByPlaceholderText('Enter your answer...');

  fireEvent.change(screen.getByPlaceholderText('Enter your answer...'), { target: { value: 'ok' } });
  fireEvent.click(screen.getByText('Continue'));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows/5/continue', expect.objectContaining({ method: 'POST' })));

  const elems = await screen.findAllByText('succeeded');
  expect(elems.length).toBeGreaterThan(0);
});

test('canceling waiting workflow does not send continue request', async () => {
  fetch.mockImplementation((url, options) => {
    if (url === '/workflows' && !options) {
      return mockResponse([{ id: '7', template: 'deepresearch', status: 'needs_input' }]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    if (url === '/workflows/7') {
      return mockResponse({
        id: '7',
        template: 'deepresearch',
        status: 'needs_input',
        result: { __interrupt__: [{ value: { questions: ['clarify?'] } }] }
      });
    }
    return mockResponse({});
  });

  render(<App />);

  await screen.findByText('needs_input');
  await screen.findByText('Cancel');
  fireEvent.click(screen.getByText('Cancel'));

  await waitFor(() => {});

  expect(fetch).not.toHaveBeenCalledWith('/workflows/7/continue', expect.objectContaining({ method: 'POST' }));
});

test('user can cancel running workflow', async () => {
  fetch.mockImplementation((url, options) => {
    if (url === '/workflows' && !options) {
      return mockResponse([{ id: '9', template: 'deepresearch', status: 'running' }]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    if (url === '/workflows/9') {
      return mockResponse({ id: '9', template: 'deepresearch', status: 'running', result: {} });
    }
    if (url === '/workflows/9/cancel') {
      return mockResponse({ id: '9', template: 'deepresearch', status: 'canceled', result: {} });
    }
    return mockResponse({});
  });

  render(<App />);

  await screen.findByText('running');
  const btn = await screen.findByText('Cancel Workflow');
  fireEvent.click(btn);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows/9/cancel', expect.objectContaining({ method: 'POST' })));

  const canceledElems = await screen.findAllByText('canceled');
  expect(canceledElems.length).toBeGreaterThan(0);
});

test('polls workflows periodically', async () => {
  fetch.mockImplementation((url) => {
    if (url === '/workflows') {
      return mockResponse([]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    return mockResponse({});
  });

  render(<App />);

  const timer = require('./timer');
  await waitFor(() => expect(timer.startPolling).toHaveBeenCalledTimes(1));
});

test('polls selected workflow only when running', async () => {
  fetch.mockImplementation((url) => {
    if (url === '/workflows') {
      return mockResponse([{ id: '1', template: 'a', status: 'running' }]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    if (url === '/workflows/1') {
      return mockResponse({ id: '1', template: 'a', status: 'running', result: {} });
    }
    return mockResponse({});
  });

  render(<App />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows/1'));

  const timer = require('./timer');
  expect(timer.startPolling).toHaveBeenCalledTimes(2); // list + selected
});

test('does not poll selected workflow when not running', async () => {
  fetch.mockImplementation((url) => {
    if (url === '/workflows') {
      return mockResponse([{ id: '1', template: 'a', status: 'succeeded' }]);
    }
    if (url === '/workflow-templates') {
      return mockResponse([]);
    }
    if (url === '/workflows/1') {
      return mockResponse({ id: '1', template: 'a', status: 'succeeded', result: {} });
    }
    return mockResponse({});
  });

  render(<App />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows/1'));

  const timer = require('./timer');
  expect(timer.startPolling).toHaveBeenCalledTimes(1); // only list
});

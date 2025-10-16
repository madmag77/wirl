import '@testing-library/jest-dom'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

jest.mock('./constants', () => ({
  API_BASE_URL: '',
  POLL_INTERVAL_MS: 10000
}))

jest.mock('./timer', () => ({
  startPolling: jest.fn(cb => {
    cb()
    return 1
  })
}))

import App from './App'

jest.mock('react-markdown', () => {
  return function ReactMarkdown({ children }) {
    return <div data-testid="markdown-content">{children}</div>
  }
})

beforeEach(() => {
  global.fetch = jest.fn()
})

afterEach(() => {
  jest.resetAllMocks()
})

function mockResponse(data) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(data) })
}

test('workflows display in succeeded, running and waiting states', async () => {
  const workflows = [
    { id: '1', template: 'a', status: 'running', created_at: '2024-01-01T00:00:00Z' },
    { id: '2', template: 'b', status: 'needs_input', created_at: '2024-01-02T00:00:00Z' },
    { id: '3', template: 'c', status: 'succeeded', created_at: '2024-01-03T00:00:00Z' }
  ]
  const details = {
    1: { id: '1', template: 'a', status: 'running', inputs: {}, result: {} },
    2: { id: '2', template: 'b', status: 'needs_input', inputs: {}, result: {} },
    3: { id: '3', template: 'c', status: 'succeeded', inputs: {}, result: {} }
  }

  fetch.mockImplementation(url => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?')) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows/')) {
      const id = url.split('/')[2]
      return mockResponse(details[id])
    }
    return mockResponse({})
  })

  render(<App />)

  await screen.findAllByRole('table')

  await waitFor(() => {
    expect(document.querySelector('.status-pill.status-running')).toBeTruthy()
    expect(document.querySelector('.status-pill.status-needs-input')).toBeTruthy()
    expect(document.querySelector('.status-pill.status-succeeded')).toBeTruthy()
  })
})

test('user can start new workflow with selected template', async () => {
  let workflows = []
  const details = {}

  fetch.mockImplementation((url, options) => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?') && !options) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([
        { id: 'deepresearch', name: 'DeepResearch' },
        { id: 'example', name: 'Example' }
      ])
    }
    if (url === '/workflows' && options?.method === 'POST') {
      const body = JSON.parse(options.body)
      expect(body.template_name).toBe('example')
      expect(body.inputs.query).toBe('my query')
      workflows = [
        { id: '10', template: 'example', status: 'running', created_at: '2024-02-10T10:00:00Z' }
      ]
      details['10'] = { id: '10', template: 'example', status: 'running', inputs: {}, result: {} }
      return mockResponse({ id: '10', template: 'example', status: 'running', result: {} })
    }
    if (url.startsWith('/workflows/') && !options) {
      const id = url.split('/')[2]
      return mockResponse(details[id] ?? { id, template: 'example', status: 'running', inputs: {}, result: {} })
    }
    return mockResponse({})
  })

  render(<App />)

  fireEvent.click(await screen.findByText(/Start New Workflow/))

  await screen.findByText('Start')
  fireEvent.change(screen.getByPlaceholderText('Enter query...'), { target: { value: 'my query' } })
  fireEvent.change(screen.getByTestId('template-select'), { target: { value: 'example' } })
  fireEvent.click(screen.getByText('Start'))

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows', expect.objectContaining({ method: 'POST' })))

  await screen.findByText('example')
  const runningBadges = document.querySelectorAll('.status-pill.status-running')
  expect(runningBadges.length).toBeGreaterThan(0)
})

test('canceling new workflow does not start it', async () => {
  fetch.mockImplementation((url, options) => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?') && !options) {
      return mockResponse({ items: [], total: 0, limit: 0, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([{ id: 'deepresearch', name: 'DeepResearch' }])
    }
    if (url === '/workflows' && options?.method === 'POST') {
      throw new Error('Should not be called')
    }
    return mockResponse({})
  })

  render(<App />)

  fireEvent.click(await screen.findByText(/Start New Workflow/))
  await screen.findByText('Start')
  fireEvent.click(screen.getByText('Cancel'))

  await waitFor(() => { })
  expect(fetch).not.toHaveBeenCalledWith('/workflows', expect.objectContaining({ method: 'POST' }))
})

test('user can continue waiting workflow', async () => {
  let workflows = [
    { id: '5', template: 'deepresearch', status: 'needs_input', created_at: '2024-03-01T10:00:00Z' }
  ]
  const details = {
    5: {
      id: '5',
      template: 'deepresearch',
      status: 'needs_input',
      inputs: {},
      result: { __interrupt__: [{ value: { questions: ['clarify?'] } }] }
    }
  }

  fetch.mockImplementation((url, options) => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?') && !options) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/5' && !options) {
      return mockResponse(details[5])
    }
    if (url === '/workflows/5/continue') {
      workflows = [
        { id: '5', template: 'deepresearch', status: 'succeeded', created_at: '2024-03-01T10:00:00Z' }
      ]
      details[5] = { id: '5', template: 'deepresearch', status: 'succeeded', inputs: {}, result: { final_answer: 'done' } }
      return mockResponse({ id: '5', template: 'deepresearch', status: 'succeeded', result: { final_answer: 'done' } })
    }
    return mockResponse({})
  })

  render(<App />)

  fireEvent.click(await screen.findByTestId('workflow-row-5'))

  await screen.findByPlaceholderText('Enter your answer...')
  fireEvent.change(screen.getByPlaceholderText('Enter your answer...'), { target: { value: 'ok' } })
  const modal = screen.getByRole('dialog')
  fireEvent.click(within(modal).getByRole('button', { name: 'Continue' }))

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows/5/continue', expect.objectContaining({ method: 'POST' })))

  const succeededBadges = await screen.findAllByText('succeeded')
  expect(succeededBadges.length).toBeGreaterThan(0)
})

test('canceling waiting workflow does not send continue request', async () => {
  const workflows = [
    { id: '7', template: 'deepresearch', status: 'needs_input', created_at: '2024-03-01T10:00:00Z' }
  ]
  const details = {
    7: {
      id: '7',
      template: 'deepresearch',
      status: 'needs_input',
      inputs: {},
      result: { __interrupt__: [{ value: { questions: ['clarify?'] } }] }
    }
  }

  fetch.mockImplementation((url, options) => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?') && !options) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/7' && !options) {
      return mockResponse(details[7])
    }
    if (url === '/workflows/7/continue') {
      throw new Error('Should not be called')
    }
    return mockResponse({})
  })

  render(<App />)

  fireEvent.click(await screen.findByTestId('workflow-row-7'))
  await screen.findByPlaceholderText('Enter your answer...')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

  await waitFor(() => { })
  expect(fetch).not.toHaveBeenCalledWith('/workflows/7/continue', expect.objectContaining({ method: 'POST' }))
})

test('user can cancel running workflow', async () => {
  let workflows = [
    { id: '9', template: 'deepresearch', status: 'running', created_at: '2024-04-01T09:00:00Z' }
  ]
  const details = {
    9: { id: '9', template: 'deepresearch', status: 'running', inputs: {}, result: {} }
  }

  fetch.mockImplementation((url, options) => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?') && !options) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/9' && !options) {
      return mockResponse(details[9])
    }
    if (url === '/workflows/9/cancel') {
      workflows = [
        { id: '9', template: 'deepresearch', status: 'canceled', created_at: '2024-04-01T09:00:00Z' }
      ]
      details[9] = { id: '9', template: 'deepresearch', status: 'canceled', inputs: {}, result: {} }
      return mockResponse({ id: '9', template: 'deepresearch', status: 'canceled', result: {} })
    }
    return mockResponse({})
  })

  render(<App />)

  fireEvent.click(await screen.findByTestId('workflow-row-9'))
  await screen.findByText('Cancel Workflow')
  fireEvent.click(screen.getByText('Cancel Workflow'))

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/workflows/9/cancel', expect.objectContaining({ method: 'POST' })))

  const canceledBadges = await screen.findAllByText('canceled')
  expect(canceledBadges.length).toBeGreaterThan(0)
})

test('polls workflows periodically', async () => {
  const workflows = [
    { id: 'poll-1', template: 'news', status: 'running', created_at: '2024-05-01T12:00:00Z' }
  ]
  const details = {
    'poll-1': { id: 'poll-1', template: 'news', status: 'running', inputs: {}, result: {} }
  }

  fetch.mockImplementation(url => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?')) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/poll-1') {
      return mockResponse(details['poll-1'])
    }
    return mockResponse({})
  })

  render(<App />)

  const timer = require('./timer')
  await waitFor(() => expect(timer.startPolling).toHaveBeenCalledTimes(1))
})

test('polls selected workflow only when running', async () => {
  const workflows = [
    { id: '1', template: 'a', status: 'running', created_at: '2024-05-01T12:00:00Z' }
  ]
  const details = {
    1: { id: '1', template: 'a', status: 'running', inputs: {}, result: {} }
  }

  fetch.mockImplementation(url => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?')) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/1') {
      return mockResponse(details[1])
    }
    return mockResponse({})
  })

  render(<App />)

  const timer = require('./timer')
  await waitFor(() => expect(timer.startPolling).toHaveBeenCalledTimes(3))
})

test('does not poll selected workflow when not running', async () => {
  const workflows = [
    { id: '1', template: 'a', status: 'succeeded', created_at: '2024-05-01T12:00:00Z' }
  ]
  const details = {
    1: { id: '1', template: 'a', status: 'succeeded', inputs: {}, result: {} }
  }

  fetch.mockImplementation(url => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?')) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/1') {
      return mockResponse(details[1])
    }
    return mockResponse({})
  })

  render(<App />)

  const timer = require('./timer')
  await waitFor(() => expect(timer.startPolling).toHaveBeenCalledTimes(0))
})

test('opens modal when thread_id is in URL query parameter', async () => {
  const originalHref = window.location.href
  window.history.pushState({}, '', '?thread_id=hitl-123')

  const workflows = [
    { id: 'hitl-123', template: 'deepresearch', status: 'needs_input', created_at: '2024-06-01T10:00:00Z' }
  ]
  const details = {
    'hitl-123': {
      id: 'hitl-123',
      template: 'deepresearch',
      status: 'needs_input',
      inputs: {},
      result: { __interrupt__: [{ value: { questions: ['What is your answer?'] } }] }
    }
  }

  fetch.mockImplementation(url => {
    if (url === '/workflow-triggers') {
      return mockResponse([])
    }
    if (url.startsWith('/workflows?')) {
      return mockResponse({ items: workflows, total: workflows.length, limit: workflows.length, offset: 0 })
    }
    if (url === '/workflow-templates') {
      return mockResponse([])
    }
    if (url === '/workflows/hitl-123') {
      return mockResponse(details['hitl-123'])
    }
    return mockResponse({})
  })

  render(<App />)

  // Modal should open automatically with the workflow details
  const modal = await screen.findByRole('dialog')
  expect(within(modal).getByText('What is your answer?')).toBeInTheDocument()
  expect(within(modal).getByPlaceholderText('Enter your answer...')).toBeInTheDocument()

  // Restore original location
  window.history.pushState({}, '', originalHref)
})

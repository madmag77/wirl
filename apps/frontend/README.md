# Frontend

This is a simple React project powered by [Vite](https://vitejs.dev). It provides a UI for browsing existing workflows and starting new ones using the backend API.

## Available Scripts

```
npm install
npm run dev
```

The app displays a sidebar with workflow history on the left and the selected workflow details on the right. A "Start New Workflow" button prompts for a query and launches the `deepresearch` workflow via the backend API. If the workflow is waiting for user input, a text box is shown to continue the run.

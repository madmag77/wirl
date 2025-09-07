import { API_BASE_URL } from './constants.js'

// Base URL configuration - can be overridden via environment variables
const BASE_URL = API_BASE_URL

/**
 * Fetch list of workflow runs.
 * @returns {Promise<WorkflowHistory[]>}
 */
export async function getWorkflows() {
  const resp = await fetch(`${BASE_URL}/workflows`)
  return resp.json()
}

/**
 * Fetch available workflow templates.
 * @returns {Promise<TemplateInfo[]>}
 */
export async function getWorkflowTemplates() {
  const resp = await fetch(`${BASE_URL}/workflow-templates`)
  return resp.json()
}

/**
 * Fetch workflow details.
 * @param {string} id
 * @returns {Promise<WorkflowDetail>}
 */
export async function getWorkflow(id) {
  const resp = await fetch(`${BASE_URL}/workflows/${id}`)
  return resp.json()
}

/**
 * Start a new workflow.
 * @param {string} template
 * @param {string} query
 * @returns {Promise<WorkflowResponse>}
 */
export async function startWorkflow(template, query) {
  const resp = await fetch(`${BASE_URL}/workflows`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_name: template, query })
  })
  return resp.json()
}

/**
 * Continue a workflow waiting for input.
 * @param {string} id
 * @param {string} answer
 * @returns {Promise<WorkflowResponse>}
 */
export async function continueWorkflow(id, answer) {
  const resp = await fetch(`${BASE_URL}/workflows/${id}/continue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: answer })
  })
  return resp.json()
}

/**
 * Cancel a running workflow.
 * @param {string} id
 * @returns {Promise<WorkflowResponse>}
 */
export async function cancelWorkflow(id) {
  const resp = await fetch(`${BASE_URL}/workflows/${id}/cancel`, {
    method: 'POST'
  })
  return resp.json()
}

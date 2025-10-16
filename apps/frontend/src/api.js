import { API_BASE_URL } from './constants.js'

// Base URL configuration - can be overridden via environment variables
const BASE_URL = API_BASE_URL

async function handleJsonResponse(resp) {
  if (!resp.ok) {
    let message = `HTTP ${resp.status}: ${resp.statusText}`
    try {
      const body = await resp.json()
      if (typeof body?.detail === 'string') {
        message = body.detail
      }
    } catch (error) {
      // Ignore JSON parsing errors for failed responses
    }
    throw new Error(message)
  }
  return resp.json()
}

/**
 * Fetch list of workflow runs.
 * @param {Object} [options]
 * @param {number} [options.limit]
 * @param {number} [options.offset]
 * @returns {Promise<WorkflowHistoryPage>}
 */
export async function getWorkflows({ limit = 10, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const resp = await fetch(`${BASE_URL}/workflows?${params.toString()}`)
  return handleJsonResponse(resp)
}

/**
 * Fetch available workflow templates.
 * @returns {Promise<TemplateInfo[]>}
 */
export async function getWorkflowTemplates() {
  const resp = await fetch(`${BASE_URL}/workflow-templates`)
  return handleJsonResponse(resp)
}

/**
 * Fetch workflow details.
 * @param {string} id
 * @returns {Promise<WorkflowDetail>}
 */
export async function getWorkflow(id) {
  const resp = await fetch(`${BASE_URL}/workflows/${id}`)
  return handleJsonResponse(resp)
}

/**
 * Fetch detailed run information for a workflow.
 * @param {string} id
 * @returns {Promise<WorkflowRunDetails>}
 */
export async function getWorkflowRunDetails(id) {
  const resp = await fetch(`${BASE_URL}/workflows/${id}/run-details`)
  return handleJsonResponse(resp)
}

/**
 * Start a new workflow.
 * @param {string} template
 * @param {string} query
 * @returns {Promise<WorkflowResponse>}
 */
export async function startWorkflow(template, query) {
  let inputs = {}
  if (query && query.trim().length > 0) {
    try {
      inputs = JSON.parse(query)
    } catch (error) {
      inputs = { query }
    }
  }
  const resp = await fetch(`${BASE_URL}/workflows`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_name: template, inputs })
  })
  return handleJsonResponse(resp)
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
    body: JSON.stringify({ inputs: { answer } })
  })
  return handleJsonResponse(resp)
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
  return handleJsonResponse(resp)
}

/**
 * Fetch configured workflow triggers.
 * @returns {Promise<WorkflowTriggerResponse[]>}
 */
export async function getWorkflowTriggers() {
  const resp = await fetch(`${BASE_URL}/workflow-triggers`)
  return handleJsonResponse(resp)
}

/**
 * Create a new workflow trigger.
 * @param {Object} payload
 * @returns {Promise<WorkflowTriggerResponse>}
 */
export async function createWorkflowTrigger(payload) {
  const resp = await fetch(`${BASE_URL}/workflow-triggers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleJsonResponse(resp)
}

/**
 * Update an existing workflow trigger.
 * @param {string} id
 * @param {Object} payload
 * @returns {Promise<WorkflowTriggerResponse>}
 */
export async function updateWorkflowTrigger(id, payload) {
  const resp = await fetch(`${BASE_URL}/workflow-triggers/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  return handleJsonResponse(resp)
}

/**
 * Delete a workflow trigger.
 * @param {string} id
 * @returns {Promise<void>}
 */
export async function deleteWorkflowTrigger(id) {
  const resp = await fetch(`${BASE_URL}/workflow-triggers/${id}`, {
    method: 'DELETE'
  })
  if (!resp.ok) {
    let message = `HTTP ${resp.status}: ${resp.statusText}`
    try {
      const body = await resp.json()
      if (typeof body?.detail === 'string') {
        message = body.detail
      }
    } catch (error) {
      // Ignore JSON parsing errors
    }
    throw new Error(message)
  }
}

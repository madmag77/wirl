/**
 * @typedef {'queued' | 'running' | 'needs_input' | 'failed' | 'succeeded' | 'canceled'} WorkflowStatus
 */

/**
 * @typedef {Object} WorkflowHistory
 * @property {string} id
 * @property {string} template
 * @property {WorkflowStatus} status
 * @property {string} created_at
 */

/**
 * @typedef {Object} WorkflowDetail
 * @property {string} id
 * @property {string} template
 * @property {WorkflowStatus} status
 * @property {Object} result
 */

/**
 * @typedef {Object} WorkflowResponse
 * @property {string} id
 * @property {WorkflowStatus} status
 * @property {Object} [result]
 */

/**
 * @typedef {Object} TemplateInfo
 * @property {string} id
 * @property {string} name
 * @property {string} path
 */

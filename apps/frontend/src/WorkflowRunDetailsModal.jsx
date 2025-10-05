import { useEffect, useState } from 'react'
import { getWorkflowRunDetails } from './api.js'

function formatJson(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (error) {
    return String(value)
  }
}

function formatTimestamp(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

export default function WorkflowRunDetailsModal({ runId, onClose }) {
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    if (!runId) {
      setDetails(null)
      setLoading(false)
      setError(null)
      return undefined
    }

    setLoading(true)
    setError(null)
    getWorkflowRunDetails(runId)
      .then(data => {
        if (!cancelled) {
          setDetails(data)
          setLoading(false)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [runId])

  if (!runId) {
    return null
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal run-details-modal" onClick={event => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Run Details</h3>
            <p className="modal-subtitle">Complete execution trace for this workflow run.</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close run details">×</button>
        </div>

        {loading && <p className="run-details-status">Loading run information…</p>}
        {error && (
          <p className="run-details-status error">Failed to load run details: {error.message ?? String(error)}</p>
        )}

        {!loading && !error && details && (
          <>
            <section className="run-details-section">
              <h4>Initial State</h4>
              <pre className="detail-pre">{formatJson(details.initial_state)}</pre>
            </section>

            <section className="run-details-section">
              <h4>Execution Steps</h4>
              {details.steps.length === 0 ? (
                <p className="run-details-status">No execution data recorded for this run.</p>
              ) : (
                <div className="run-steps">
                  {details.steps.map(step => (
                    <article key={`${step.step}-${step.task_id}`} className="run-step-card">
                      <header className="run-step-header">
                        <div>
                          <span className="step-label">Step {step.step}</span>
                          <span className="step-node">Node: {step.node ?? 'Unknown node'}</span>
                        </div>
                        <div className="step-meta">
                          <span>Task: {step.task_id}</span>
                          <span>{formatTimestamp(step.timestamp)}</span>
                        </div>
                      </header>

                      <div className="run-step-grid">
                        <div>
                          <h5>Input</h5>
                          <pre className="detail-pre">{formatJson(step.input_state)}</pre>
                        </div>
                        <div>
                          <h5>Output</h5>
                          <pre className="detail-pre">{formatJson(step.output_state)}</pre>
                        </div>
                      </div>

                      {step.branches && step.branches.length > 0 && (
                        <div className="run-step-branches">
                          <h5>Scheduled Next Nodes</h5>
                          <ul>
                            {step.branches.map(branch => (
                              <li key={branch}>{branch}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {step.writes && step.writes.length > 0 && (
                        <div className="run-step-writes">
                          <h5>Writes</h5>
                          <ul>
                            {step.writes.map((write, index) => (
                              <li key={`${write.channel}-${index}`}>
                                <span className={`write-kind write-kind-${write.kind}`}>{write.kind}</span>
                                <span className="write-channel">{write.channel}</span>
                                <pre className="detail-pre inline-pre">{formatJson(write.value)}</pre>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

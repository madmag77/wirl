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

function calculateDuration(currentTimestamp, nextTimestamp) {
  if (!currentTimestamp || !nextTimestamp) return null
  const current = new Date(currentTimestamp)
  const next = new Date(nextTimestamp)
  if (Number.isNaN(current.getTime()) || Number.isNaN(next.getTime())) return null
  const durationMs = next - current
  if (durationMs < 0) return null

  // Format duration nicely
  if (durationMs < 1000) {
    return `${durationMs}ms`
  } else if (durationMs < 60000) {
    return `${(durationMs / 1000).toFixed(2)}s`
  } else {
    const minutes = Math.floor(durationMs / 60000)
    const seconds = ((durationMs % 60000) / 1000).toFixed(0)
    return `${minutes}m ${seconds}s`
  }
}

export default function WorkflowRunDetailsModal({ runId, onClose }) {
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [collapsedWrites, setCollapsedWrites] = useState(new Set())

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

  // Initialize all writes as collapsed when details load
  useEffect(() => {
    if (details?.steps) {
      const allStepKeys = new Set(
        details.steps
          .map((step, idx) => `${step.step}-${step.task_id}-${idx}`)
          .filter((_, idx) => details.steps[idx].writes?.length > 0)
      )
      setCollapsedWrites(allStepKeys)
    }
  }, [details])

  const toggleWritesCollapsed = (stepKey) => {
    setCollapsedWrites(prev => {
      const newSet = new Set(prev)
      if (newSet.has(stepKey)) {
        newSet.delete(stepKey)
      } else {
        newSet.add(stepKey)
      }
      return newSet
    })
  }

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
                  {details.steps.map((step, idx) => {
                    const stepKey = `${step.step}-${step.task_id}-${idx}`
                    const nextStep = details.steps[idx + 1]
                    const duration = nextStep ? calculateDuration(step.timestamp, nextStep.timestamp) : null
                    const isWritesCollapsed = collapsedWrites.has(stepKey)

                    return (
                      <article key={stepKey} className="run-step-card">
                        <header className="run-step-header">
                          <div>
                            <span className="step-label">Step {step.step}</span>
                            <span className="step-node">Node: {step.node ?? 'Unknown node'}</span>
                          </div>
                          <div className="step-meta">
                            <span>Task: {step.task_id}</span>
                            <span>
                              {formatTimestamp(step.timestamp)}
                              {duration && <span className="step-duration"> ({duration})</span>}
                            </span>
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
                            <div
                              className="writes-header"
                              onClick={() => toggleWritesCollapsed(stepKey)}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault()
                                  toggleWritesCollapsed(stepKey)
                                }
                              }}
                            >
                              <h5>Writes</h5>
                              <span className="toggle-icon">{isWritesCollapsed ? '▶' : '▼'}</span>
                            </div>
                            {!isWritesCollapsed && (
                              <ul>
                                {step.writes.map((write, index) => (
                                  <li key={`${write.channel}-${index}`}>
                                    <span className={`write-kind write-kind-${write.kind}`}>{write.kind}</span>
                                    <span className="write-channel">{write.channel}</span>
                                    <pre className="detail-pre inline-pre">{formatJson(write.value)}</pre>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                      </article>
                    )
                  })}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

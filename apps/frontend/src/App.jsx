import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import {
  cancelWorkflow as apiCancel,
  continueWorkflow as apiContinue,
  startWorkflow as apiStart,
  getWorkflow,
  getWorkflows,
  getWorkflowTemplates,
} from './api.js'
import WorkflowRunDetailsModal from './WorkflowRunDetailsModal.jsx'
import { POLL_INTERVAL_MS } from './constants.js'
import { startPolling } from './timer.js'

export default function App() {
  const [workflows, setWorkflows] = useState([])
  const [workflowDetails, setWorkflowDetails] = useState({})
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [showDetailsModal, setShowDetailsModal] = useState(false)
  const [showRunDetailsModal, setShowRunDetailsModal] = useState(false)
  const [runDetailsId, setRunDetailsId] = useState(null)
  const [showInterrupt, setShowInterrupt] = useState(false)
  const [expandedSections, setExpandedSections] = useState({
    inputs: true,
    results: true,
    error: true
  })
  const [templates, setTemplates] = useState([])
  const [showStartModal, setShowStartModal] = useState(false)
  const [newTemplate, setNewTemplate] = useState('')
  const [newQuery, setNewQuery] = useState('')
  const [answer, setAnswer] = useState('')

  const workflowDetailsRef = useRef({})
  const isMountedRef = useRef(true)

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const refreshWorkflows = useCallback(async (fetchDetails = false) => {
    const list = await getWorkflows()
    setWorkflows(list)

    // Only fetch details when explicitly requested or for new workflows
    if (fetchDetails) {
      const detailEntries = await Promise.all(
        list.map(async workflow => {
          try {
            // Only fetch if we don't have details or workflow is running
            if (!workflowDetailsRef.current[workflow.id] || workflow.status === 'running') {
              const detail = await getWorkflow(workflow.id)
              return [workflow.id, detail]
            }
            return [workflow.id, workflowDetailsRef.current[workflow.id]]
          } catch (error) {
            console.error('Failed to fetch workflow detail', error)
            return null
          }
        })
      )

      if (!isMountedRef.current) {
        return list
      }

      const nextDetails = {}
      for (const workflow of list) {
        const detailEntry = detailEntries.find(entry => entry && entry[0] === workflow.id)
        if (detailEntry) {
          nextDetails[workflow.id] = detailEntry[1]
        } else if (workflowDetailsRef.current[workflow.id]) {
          nextDetails[workflow.id] = workflowDetailsRef.current[workflow.id]
        }
      }

      workflowDetailsRef.current = nextDetails
      setWorkflowDetails(nextDetails)
    }

    return list
  }, [])

  useEffect(() => {
    let intervalId
    let timeoutId

    const load = async (fetchDetails = false) => {
      const data = await refreshWorkflows(fetchDetails)
      setSelectedId(current => {
        if (current && data.some(item => item.id === current)) {
          return current
        }
        if (data.length > 0) {
          return data[0].id
        }
        return null
      })
      return data
    }

    const setupPolling = async () => {
      // Clear any existing timers
      if (intervalId) clearInterval(intervalId)
      if (timeoutId) clearTimeout(timeoutId)

      const data = await load(true) // Fetch details on initial load
      const hasRunningWorkflows = data.some(workflow => workflow.status === 'running')

      if (hasRunningWorkflows) {
        intervalId = startPolling(async () => {
          const updatedData = await load(false) // Don't fetch details on every poll
          const stillHasRunning = updatedData.some(workflow => workflow.status === 'running')
          if (!stillHasRunning) {
            clearInterval(intervalId)
            intervalId = null
            // Schedule next check
            timeoutId = setTimeout(setupPolling, POLL_INTERVAL_MS * 5)
          }
        }, POLL_INTERVAL_MS)
      } else {
        // If no running workflows, check again after a longer delay
        timeoutId = setTimeout(setupPolling, POLL_INTERVAL_MS * 5)
      }
    }

    setupPolling()

    return () => {
      if (intervalId) clearInterval(intervalId)
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [refreshWorkflows])

  useEffect(() => {
    getWorkflowTemplates().then(data => {
      setTemplates(data)
      if (data.length > 0) {
        setNewTemplate(data[0].id)
      }
    })
  }, [])

  // Handle deep linking with thread_id query parameter
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const threadId = params.get('thread_id')

    if (threadId) {
      // Wait a bit for workflows to load, then open the modal
      const timer = setTimeout(() => {
        const workflow = workflows.find(w => w.id === threadId)
        if (workflow) {
          openDetailsModal(threadId)
        } else {
          // If not in list yet, try to fetch it directly
          getWorkflow(threadId).then(data => {
            workflowDetailsRef.current = {
              ...workflowDetailsRef.current,
              [data.id]: data
            }
            setWorkflowDetails(current => ({
              ...current,
              [data.id]: data
            }))
            setSelectedId(threadId)
            setShowDetailsModal(true)
            if (data.status === 'needs_input') {
              setShowInterrupt(true)
            }
          }).catch(error => {
            console.error('Failed to fetch workflow from URL', error)
          })
        }
      }, 100)

      return () => clearTimeout(timer)
    }
  }, [workflows])

  useEffect(() => {
    if (!selectedId) {
      setSelected(null)
      return
    }

    const detail = workflowDetails[selectedId]
    if (detail) {
      setSelected(detail)
      return
    }

    // Only fetch if we don't have the detail already
    if (!workflowDetailsRef.current[selectedId]) {
      getWorkflow(selectedId).then(data => {
        workflowDetailsRef.current = {
          ...workflowDetailsRef.current,
          [data.id]: data
        }
        setWorkflowDetails(current => ({
          ...current,
          [data.id]: data
        }))
        setSelected(data)
      })
    }
  }, [selectedId, workflowDetails])

  useEffect(() => {
    if (!selectedId || selected?.status !== 'running') return

    const fetchSelected = () => {
      getWorkflow(selectedId).then(data => {
        workflowDetailsRef.current = {
          ...workflowDetailsRef.current,
          [data.id]: data
        }
        setWorkflowDetails(current => ({
          ...current,
          [data.id]: data
        }))
        setSelected(data)
      })
    }

    const id = startPolling(fetchSelected, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [selectedId, selected?.status])

  useEffect(() => {
    if (selected && selected.status === 'needs_input') {
      setShowInterrupt(true)
    } else {
      setShowInterrupt(false)
    }
  }, [selected])

  const openStartModal = () => {
    setNewQuery('')
    if (templates.length > 0) {
      setNewTemplate(templates[0].id)
    }
    setShowStartModal(true)
  }

  const confirmStartWorkflow = async () => {
    setShowStartModal(false)
    const data = await apiStart(newTemplate, newQuery)
    setSelectedId(data.id)
    setShowDetailsModal(true)
    await refreshWorkflows()
  }

  const cancelStartWorkflow = () => {
    setShowStartModal(false)
  }

  const continueWorkflow = async answerValue => {
    if (!selectedId) return

    const data = await apiContinue(selectedId, answerValue)
    setWorkflows(prev => prev.map(w => (w.id === selectedId ? { ...w, status: data.status } : w)))
    setSelected(current => (current ? { ...current, status: data.status, result: data.result ?? current.result } : data))
    setWorkflowDetails(current => {
      const next = {
        ...current,
        [selectedId]: {
          ...(current[selectedId] ?? {}),
          status: data.status,
          result: data.result ?? current[selectedId]?.result ?? {}
        }
      }
      workflowDetailsRef.current = next
      return next
    })
    setShowInterrupt(false)
  }

  const cancelRunningWorkflow = async () => {
    if (!selectedId) return

    const data = await apiCancel(selectedId)
    setWorkflows(prev => prev.map(w => (w.id === selectedId ? { ...w, status: data.status } : w)))
    setSelected(current => (current ? { ...current, status: data.status, result: data.result ?? current.result } : data))
    setWorkflowDetails(current => {
      const next = {
        ...current,
        [selectedId]: {
          ...(current[selectedId] ?? {}),
          status: data.status,
          result: data.result ?? current[selectedId]?.result ?? {}
        }
      }
      workflowDetailsRef.current = next
      return next
    })
  }

  const toggleSection = section => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const formatDateTime = value => {
    if (!value) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return value
    }
    return date.toLocaleString()
  }


  const openDetailsModal = id => {
    setExpandedSections({ inputs: true, results: true, error: true })
    setSelectedId(id)
    setShowDetailsModal(true)

    // Check if we need to show interrupt section
    const workflow = workflows.find(w => w.id === id)
    if (workflow?.status === 'needs_input') {
      setShowInterrupt(true)
    }

    if (!workflowDetails[id]) {
      getWorkflow(id).then(data => {
        workflowDetailsRef.current = {
          ...workflowDetailsRef.current,
          [data.id]: data
        }
        setWorkflowDetails(current => ({
          ...current,
          [data.id]: data
        }))
        setSelected(data)
        // Also set showInterrupt if status is needs_input
        if (data.status === 'needs_input') {
          setShowInterrupt(true)
        }
      })
    }
  }

  const closeDetailsModal = () => {
    setShowDetailsModal(false)
    setShowInterrupt(false)
    setAnswer('')
    setShowRunDetailsModal(false)
    setRunDetailsId(null)
  }

  const openRunDetailsModal = id => {
    setRunDetailsId(id)
    setShowRunDetailsModal(true)
  }

  const closeRunDetailsModal = () => {
    setShowRunDetailsModal(false)
    setRunDetailsId(null)
  }

  const handleRetry = async id => {
    try {
      await apiContinue(id, null)
      await refreshWorkflows()
      setSelectedId(id)
      setShowDetailsModal(true)
    } catch (error) {
      console.error('Failed to continue workflow', error)
    }
  }

  const sortedWorkflows = [...workflows].sort((a, b) => {
    const aTime = a?.created_at ? new Date(a.created_at).getTime() : 0
    const bTime = b?.created_at ? new Date(b.created_at).getTime() : 0
    return bTime - aTime
  })

  console.log('Current workflows state:', workflows)
  console.log('Sorted workflows for table:', sortedWorkflows)

  const getDetailForRow = id => workflowDetails[id] ?? null

  const getCreatedAtForSelected = () => {
    const current = workflows.find(item => item.id === selected?.id)
    return current?.created_at
  }

  const interrupt = selected?.result?.__interrupt__?.[0]

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-titles">
          <h1>Workflow Runs</h1>
          <p className="subtitle">Track, inspect, and relaunch your workflows from a single view.</p>
        </div>
        <button className="primary-btn" onClick={openStartModal}>Start New Workflow</button>
      </header>
      <main className="app-main">
        <div className="table-card">
          <table className="workflow-table" role="table">
            <thead>
              <tr>
                <th scope="col">Date &amp; Time</th>
                <th scope="col">Workflow</th>
                <th scope="col">Status</th>
                <th scope="col" className="actions-header">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedWorkflows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="empty-state">No workflow runs yet. Start a workflow to see it here.</td>
                </tr>
              ) : (
                sortedWorkflows.map(workflow => {
                  const detail = getDetailForRow(workflow.id)
                  return (
                    <tr
                      key={workflow.id}
                      className="workflow-row"
                      onClick={() => openDetailsModal(workflow.id)}
                      data-testid={`workflow-row-${workflow.id}`}
                    >
                      <td>{formatDateTime(workflow.created_at)}</td>
                      <td>{detail?.template ?? workflow.template}</td>
                      <td>
                        <span className={`status-pill status-${workflow.status.replace(/[\s_]+/g, '-').toLowerCase()}`}>
                          {workflow.status}
                        </span>
                      </td>
                      <td className="actions-cell">
                        {workflow.status === 'failed' && (
                          <button
                            className="table-continue-btn"
                            onClick={event => {
                              event.stopPropagation()
                              handleRetry(workflow.id)
                            }}
                          >
                            Retry
                          </button>
                        )}
                        {workflow.status === 'needs_input' && (
                          <button
                            className="table-continue-btn"
                            onClick={event => {
                              event.stopPropagation()
                              openDetailsModal(workflow.id)
                            }}
                          >
                            Continue
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </main>

      {showStartModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal start-modal">
            <h3>Start Workflow</h3>
            <select data-testid="template-select" value={newTemplate} onChange={e => setNewTemplate(e.target.value)}>
              {templates.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <input
              placeholder="Enter query..."
              value={newQuery}
              onChange={e => setNewQuery(e.target.value)}
            />
            <div className="modal-buttons">
              <button className="cancel-btn" onClick={cancelStartWorkflow}>Cancel</button>
              <button className="start-btn" onClick={confirmStartWorkflow}>Start</button>
            </div>
          </div>
        </div>
      )}

      {showDetailsModal && selected && (
        <div className="modal-overlay" role="dialog" aria-modal="true" onClick={closeDetailsModal}>
          <div className="modal detail-modal" onClick={event => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{selected.template}</h3>
                <p className="modal-subtitle">Detailed run information</p>
              </div>
              <div className="modal-header-actions">
                <button
                  className="secondary-btn"
                  onClick={() => openRunDetailsModal(selected.id)}
                >
                  View Run Details
                </button>
                <button className="icon-btn" onClick={closeDetailsModal} aria-label="Close details">×</button>
              </div>
            </div>

            <div className="detail-grid">
              <div className="detail-grid-item">
                <span className="label">Run ID</span>
                <span className="value monospace">{selected.id}</span>
              </div>
              <div className="detail-grid-item">
                <span className="label">Status</span>
                <span className={`status-pill status-${selected.status.replace(/[\s_]+/g, '-').toLowerCase()}`}>
                  {selected.status}
                </span>
              </div>
              <div className="detail-grid-item">
                <span className="label">Started</span>
                <span className="value">{formatDateTime(getCreatedAtForSelected())}</span>
              </div>
            </div>

            {selected.inputs && typeof selected.inputs === 'object' && Object.keys(selected.inputs).length > 0 && (
              <div className="detail-section">
                <div className="section-header" onClick={() => toggleSection('inputs')}>
                  <h4>Inputs</h4>
                  <span className="toggle-icon">{expandedSections.inputs ? '▼' : '▶'}</span>
                </div>
                {expandedSections.inputs && (
                  <pre className="detail-pre">{JSON.stringify(selected.inputs, null, 2)}</pre>
                )}
              </div>
            )}

            {selected.result && typeof selected.result === 'object' && Object.keys(selected.result).length > 0 && (
              <div className="detail-section">
                <div className="section-header" onClick={() => toggleSection('results')}>
                  <h4>Results</h4>
                  <span className="toggle-icon">{expandedSections.results ? '▼' : '▶'}</span>
                </div>
                {expandedSections.results && (
                  <pre className="detail-pre">{JSON.stringify(selected.result, null, 2)}</pre>
                )}
              </div>
            )}

            {selected.error && (
              <div className="detail-section">
                <div className="section-header" onClick={() => toggleSection('error')}>
                  <h4>Error</h4>
                  <span className="toggle-icon">{expandedSections.error ? '▼' : '▶'}</span>
                </div>
                {expandedSections.error && (
                  <pre className="detail-pre error-data">{selected.error}</pre>
                )}
              </div>
            )}

            {selected.status === 'running' && (
              <div className="detail-actions">
                <button className="cancel-btn" onClick={cancelRunningWorkflow}>Cancel Workflow</button>
              </div>
            )}

            {showInterrupt && (
              <div className="interrupt-section">
                {interrupt && interrupt.value && interrupt.value.questions && (
                  <>
                    <h3>Questions</h3>
                    <div className="questions-list">
                      {interrupt.value.questions.map((question, idx) => (
                        <p key={idx} className="question">{question}</p>
                      ))}
                    </div>
                  </>
                )}
                {!interrupt && (
                  <h3>Workflow Needs Input</h3>
                )}
                <div className="answer-input">
                  <input
                    value={answer}
                    onChange={e => setAnswer(e.target.value)}
                    placeholder="Enter your answer..."
                    className="answer-field"
                  />
                  <div className="answer-actions">
                    <button
                      onClick={() => { continueWorkflow(answer); setAnswer('') }}
                      className="continue-btn"
                    >
                      Continue
                    </button>
                    <button
                      onClick={() => { setShowInterrupt(false); setAnswer('') }}
                      className="cancel-btn"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {showRunDetailsModal && runDetailsId && (
        <WorkflowRunDetailsModal runId={runDetailsId} onClose={closeRunDetailsModal} />
      )}
    </div>
  )
}

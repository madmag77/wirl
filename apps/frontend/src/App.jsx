import { useEffect, useState } from 'react'
import './App.css'
import { cancelWorkflow as apiCancel, continueWorkflow as apiContinue, startWorkflow as apiStart, getWorkflow, getWorkflows, getWorkflowTemplates } from './api.js'
import { POLL_INTERVAL_MS } from './constants.js'
import { startPolling } from './timer.js'

export default function App() {
  const [workflows, setWorkflows] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
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

  useEffect(() => {
    const fetchList = () => {
      getWorkflows().then(data => {
        setWorkflows(data)
        setSelectedId(current => {
          if (current === null && data.length > 0) {
            return data[0].id
          }
          return current
        })
      })
    }

    fetchList()
    const id = startPolling(fetchList, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    getWorkflowTemplates().then(data => {
      setTemplates(data)
      if (data.length > 0) {
        setNewTemplate(data[0].id)
      }
    })
  }, [])

  useEffect(() => {
    if (!selectedId) return

    getWorkflow(selectedId).then(setSelected)
  }, [selectedId])

  useEffect(() => {
    if (!selectedId || selected?.status !== 'running') return

    const fetchSelected = () => {
      getWorkflow(selectedId).then(setSelected)
    }

    const id = startPolling(fetchSelected, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [selectedId, selected?.status])

  useEffect(() => {
    if (selected && selected.status === 'needs_input' && selected.result?.__interrupt__) {
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
    setWorkflows([...workflows, { id: data.id, template: newTemplate, status: data.status }])
    setSelectedId(data.id)
    setSelected(data)
  }

  const cancelStartWorkflow = () => {
    setShowStartModal(false)
  }

  const continueWorkflow = async answer => {
    const data = await apiContinue(selectedId, answer)
    setWorkflows(workflows.map(w => (w.id === selectedId ? { ...w, status: data.status } : w)))
    setSelected(data)
    setShowInterrupt(false)
  }

  const cancelRunningWorkflow = async () => {
    const data = await apiCancel(selectedId)
    setWorkflows(workflows.map(w => (w.id === selectedId ? { ...w, status: data.status } : w)))
    setSelected(data)
  }

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const [answer, setAnswer] = useState('')
  const interrupt = selected?.result?.__interrupt__?.[0]

  // No need to extract specific workflow fields - just show inputs and results as per WorkflowDetail model

  return (
    <div className="container">
      <aside className="sidebar">
        <h2>Workflows</h2>
        <ul className="workflow-list">
          {workflows.map(w => (
            <li
              key={w.id}
              onClick={() => setSelectedId(w.id)}
              className={w.id === selectedId ? 'selected' : ''}
            >
              <span className="title">{w.template}</span>
              <span className={`state state-${w.status.replace(/[\s_]+/g, '-').toLowerCase()}`}>{w.status}</span>
            </li>
          ))}
        </ul>
        <button className="new-workflow" onClick={openStartModal}>Start New Workflow</button>
      </aside>
      <main className="content">
        {selected ? (
          <>
            <div className="workflow-header">
              <h2>{selected.template}</h2>
              <span className={`status-badge status-${selected.status.replace(/[\s_]+/g, '-').toLowerCase()}`}>
                {selected.status}
              </span>
              {selected.status === 'running' && (
                <button className="cancel-btn" onClick={cancelRunningWorkflow}>Cancel Workflow</button>
              )}
            </div>

            {showInterrupt && interrupt ? (
              <div className="interrupt-section">
                <h3>🤔 Questions</h3>
                <div className="questions-list">
                  {interrupt.value.questions.map((question, idx) => (
                    <p key={idx} className="question">{question}</p>
                  ))}
                </div>
                <div className="answer-input">
                  <input
                    value={answer}
                    onChange={e => setAnswer(e.target.value)}
                    placeholder="Enter your answer..."
                    className="answer-field"
                  />
                  <button
                    onClick={() => { continueWorkflow(answer); setAnswer(''); }}
                    className="continue-btn"
                  >
                    Continue
                  </button>
                  <button
                    onClick={() => { setShowInterrupt(false); setAnswer(''); }}
                    className="cancel-btn"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : selected ? (
              <div className="workflow-result">
                {/* Inputs */}
                {selected.inputs && typeof selected.inputs === 'object' && selected.inputs !== null && Object.keys(selected.inputs).length > 0 && (
                  <div className="result-section">
                    <div
                      className="section-header"
                      onClick={() => toggleSection('inputs')}
                    >
                      <h3>📥 Inputs</h3>
                      <span className="toggle-icon">
                        {expandedSections.inputs ? '▼' : '▶'}
                      </span>
                    </div>
                    {expandedSections.inputs && (
                      <div className="section-content">
                        <pre className="workflow-data">{JSON.stringify(selected.inputs, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                )}

                {/* Results */}
                {selected.result && typeof selected.result === 'object' && selected.result !== null && Object.keys(selected.result).length > 0 && (
                  <div className="result-section">
                    <div
                      className="section-header"
                      onClick={() => toggleSection('results')}
                    >
                      <h3>📤 Results</h3>
                      <span className="toggle-icon">
                        {expandedSections.results ? '▼' : '▶'}
                      </span>
                    </div>
                    {expandedSections.results && (
                      <div className="section-content">
                        <pre className="workflow-data">{JSON.stringify(selected.result, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                )}

                {/* Error */}
                {selected.error && typeof selected.error === 'string' && selected.error.trim() !== '' && (
                  <div className="result-section">
                    <div
                      className="section-header"
                      onClick={() => toggleSection('error')}
                    >
                      <h3>❌ Error</h3>
                      <span className="toggle-icon">
                        {expandedSections.error ? '▼' : '▶'}
                      </span>
                    </div>
                    {expandedSections.error && (
                      <div className="section-content">
                        <pre className="error-data">{selected.error}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="no-result">
                <p>No result data available</p>
              </div>
            )}
          </>
        ) : (
          <div className="no-selection">
            <p>Select a workflow to see details</p>
          </div>
        )}
      </main>
      {showStartModal && (
        <div className="modal-overlay">
          <div className="modal">
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
    </div>
  )
}

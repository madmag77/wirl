import PropTypes from 'prop-types'

export default function WorkflowTriggersTable({
  triggers,
  onCreate,
  onToggle,
  onDelete,
  formatDateTime
}) {
  return (
    <div className="table-card">
      <div className="card-header">
        <div className="card-titles">
          <h2>Scheduled Triggers</h2>
          <p className="card-description">Automatically queue workflows according to a cron schedule.</p>
        </div>
        <button type="button" className="outline-btn" onClick={onCreate}>
          Schedule Workflow
        </button>
      </div>
      <table className="workflow-table triggers-table" role="table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Workflow</th>
            <th scope="col">Schedule</th>
            <th scope="col">Next Run</th>
            <th scope="col">Status</th>
            <th scope="col" className="actions-header">Actions</th>
          </tr>
        </thead>
        <tbody>
          {triggers.length === 0 ? (
            <tr>
              <td colSpan={6} className="empty-state">
                No scheduled triggers yet. Create one to kick off workflows on a cadence.
              </td>
            </tr>
          ) : (
            triggers.map(trigger => (
              <tr key={trigger.id}>
                <td>
                  <div className="trigger-name">{trigger.name}</div>
                  {trigger.last_run_at && (
                    <div className="status-subtle">Last run {formatDateTime(trigger.last_run_at)}</div>
                  )}
                </td>
                <td>{trigger.template_name ?? trigger.template}</td>
                <td>
                  <div className="cron-expression monospace">{trigger.cron}</div>
                  <div className="timezone-tag">{trigger.timezone}</div>
                </td>
                <td>{formatDateTime(trigger.next_run_at)}</td>
                <td>
                  <div className="trigger-status">
                    <span className={`status-pill ${trigger.is_active ? 'status-active' : 'status-paused'}`}>
                      {trigger.is_active ? 'Active' : 'Paused'}
                    </span>
                    {trigger.last_error && <div className="error-badge">{trigger.last_error}</div>}
                  </div>
                </td>
                <td className="actions-cell">
                  <div className="trigger-actions">
                    <button
                      type="button"
                      className="table-action-btn"
                      onClick={() => onToggle(trigger)}
                    >
                      {trigger.is_active ? 'Pause' : 'Resume'}
                    </button>
                    <button
                      type="button"
                      className="table-action-btn table-action-danger"
                      onClick={() => onDelete(trigger)}
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

WorkflowTriggersTable.propTypes = {
  triggers: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      template_name: PropTypes.string,
      template: PropTypes.string,
      cron: PropTypes.string.isRequired,
      timezone: PropTypes.string.isRequired,
      next_run_at: PropTypes.string,
      last_run_at: PropTypes.string,
      last_error: PropTypes.string,
      is_active: PropTypes.bool.isRequired
    })
  ).isRequired,
  onCreate: PropTypes.func.isRequired,
  onToggle: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  formatDateTime: PropTypes.func.isRequired
}

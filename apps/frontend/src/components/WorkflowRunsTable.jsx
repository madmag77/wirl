import PropTypes from 'prop-types'

export default function WorkflowRunsTable({
  workflows,
  workflowDetails,
  pagination,
  onSelectRun,
  onRetry,
  onContinue,
  onPageChange,
  formatDateTime
}) {
  const total = pagination?.total ?? workflows.length
  const limit = pagination?.limit ?? workflows.length
  const offset = pagination?.offset ?? 0
  const hasPrevious = offset > 0
  const hasNext = offset + workflows.length < total
  const startIndex = total === 0 ? 0 : offset + 1
  const endIndex = Math.min(offset + workflows.length, total)

  return (
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
          {workflows.length === 0 ? (
            <tr>
              <td colSpan={4} className="empty-state">
                No workflow runs yet. Start a workflow to see it here.
              </td>
            </tr>
          ) : (
            workflows.map(workflow => {
              const detail = workflowDetails?.[workflow.id]
              return (
                <tr
                  key={workflow.id}
                  className="workflow-row"
                  onClick={() => onSelectRun(workflow.id)}
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
                          onRetry(workflow.id)
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
                          onContinue(workflow.id)
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
      <div className="table-footer">
        <div className="pagination-info">
          {total === 0
            ? 'No runs available'
            : `Showing ${startIndex}-${endIndex} of ${total}`}
        </div>
        <div className="pagination-controls">
          <button
            type="button"
            className="pagination-btn"
            onClick={() => hasPrevious && onPageChange(offset - limit)}
            disabled={!hasPrevious}
          >
            Previous
          </button>
          <button
            type="button"
            className="pagination-btn"
            onClick={() => hasNext && onPageChange(offset + limit)}
            disabled={!hasNext}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}

WorkflowRunsTable.propTypes = {
  workflows: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    created_at: PropTypes.string,
    template: PropTypes.string,
    status: PropTypes.string.isRequired
  })).isRequired,
  workflowDetails: PropTypes.object,
  pagination: PropTypes.shape({
    total: PropTypes.number,
    limit: PropTypes.number,
    offset: PropTypes.number
  }),
  onSelectRun: PropTypes.func.isRequired,
  onRetry: PropTypes.func.isRequired,
  onContinue: PropTypes.func.isRequired,
  onPageChange: PropTypes.func.isRequired,
  formatDateTime: PropTypes.func.isRequired
}

WorkflowRunsTable.defaultProps = {
  workflowDetails: {},
  pagination: {
    total: 0,
    limit: 0,
    offset: 0
  }
}

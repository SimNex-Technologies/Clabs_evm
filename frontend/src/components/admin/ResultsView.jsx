'use client';

// Per-post horizontal bar chart: an "emphasis" chart (one hue + gray) rather
// than a categorical palette, because there's one job here - who's winning -
// not telling N distinct series apart. Winner gets the accent bar AND a
// "Winner" text badge, so the result never rests on color alone. Every bar
// carries its own value as a direct label, so the chart is already its own
// table - nothing is hidden behind color or a hover state.
export default function ResultsView({ tally, ballotCount }) {
  return (
    <div className="results-view">
      <p className="status-line" style={{ margin: '0 0 16px' }}>
        {ballotCount} ballot{ballotCount === 1 ? '' : 's'} cast
      </p>
      {tally.map((post) => {
        const rows = [
          ...post.candidates.map((c) => ({ name: c.name, count: c.count })),
          { name: 'NOTA', count: post.nota, isNota: true },
        ].sort((a, b) => b.count - a.count);
        const max = Math.max(1, ...rows.map((r) => r.count));

        return (
          <div className="results-post" key={post.post_code}>
            <h3>{post.post_title}</h3>
            <div className="results-rows">
              {rows.map((row) => {
                const isWinner = row.count > 0 && row.count === max;
                return (
                  <div className="results-row" key={row.name}>
                    <div className="rlabel">
                      <span className="name-text">{row.isNota ? <em>NOTA</em> : row.name}</span>
                      {isWinner && <span className="winner-badge">Winner</span>}
                    </div>
                    <div className="rbar-track">
                      <div
                        className={`rbar-fill ${isWinner ? 'winner' : ''}`}
                        style={{ width: `${(row.count / max) * 100}%` }}
                      />
                    </div>
                    <div className="rvalue">{row.count}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

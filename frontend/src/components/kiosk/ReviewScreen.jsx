'use client';

export default function ReviewScreen({ posts, selections, onChange, onCast }) {
  return (
    <div className="kiosk-body">
      <h1 className="school-name" style={{ fontSize: 30 }}>Review Your Vote</h1>
      <p className="status-line">Check each post carefully. This cannot be changed after you cast your vote.</p>

      <div className="review-list">
        {posts.map((post, i) => {
          const candId = selections[post.id];
          const candidate = post.candidates.find((c) => c.id === candId);
          return (
            <div className="review-row" key={post.id}>
              {candidate ? (
                <img src={`/symbols/${candidate.symbol_file}`} alt="" />
              ) : (
                <div style={{ width: 56, height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, color: 'var(--muted)' }}>✕</div>
              )}
              <div className="info">
                <div className="post-title">{post.title}</div>
                <div className={`cand-name ${candidate ? '' : 'nota'}`}>
                  {candidate ? candidate.name : 'NOTA — None of the above'}
                </div>
              </div>
              <button className="change-link" onClick={() => onChange(i)}>CHANGE</button>
            </div>
          );
        })}
      </div>

      <button className="big-button green" onClick={onCast}>
        CAST VOTE
      </button>
    </div>
  );
}

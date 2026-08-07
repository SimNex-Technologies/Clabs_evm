'use client';

import { useState } from 'react';

// A brief on-screen confirmation before advancing - a bare tap-and-instantly-
// advance interaction gives no feedback that the tap actually registered,
// which invites uncertain double-taps on a touchscreen. This pause (and the
// checkmark + dimmed siblings) makes the choice feel deliberate and confirmed.
const CONFIRM_DELAY_MS = 260;

export default function PostScreen({ post, postIndex, totalPosts, onSelect }) {
  const [selected, setSelected] = useState(null); // { type: 'candidate', id } | { type: 'nota' } | null

  function choose(selection, candidateId) {
    if (selected) return; // ignore extra taps while confirming
    setSelected(selection);
    setTimeout(() => onSelect(candidateId), CONFIRM_DELAY_MS);
  }

  return (
    <div className="kiosk-body">
      <div className="post-progress">POST {postIndex + 1} OF {totalPosts}</div>
      <div className="post-pill">{post.title}</div>

      <div className={`candidate-grid ${selected ? 'has-selection' : ''}`}>
        {post.candidates.map((c) => {
          const isSelected = selected?.type === 'candidate' && selected.id === c.id;
          return (
            <button
              key={c.id}
              className={`candidate-tile ${isSelected ? 'selected' : ''}`}
              onClick={() => choose({ type: 'candidate', id: c.id }, c.id)}
            >
              {isSelected && <span className="selected-check">✓</span>}
              <img src={`/symbols/${c.symbol_file}`} alt="" />
              <span className="candidate-name">{c.name}</span>
            </button>
          );
        })}

        <button
          className={`candidate-tile nota-tile ${selected?.type === 'nota' ? 'selected' : ''}`}
          onClick={() => choose({ type: 'nota' }, null)}
        >
          {selected?.type === 'nota' && <span className="selected-check">✓</span>}
          <span className="nota-mark">✕</span>
          <span className="candidate-name">NOTA</span>
        </button>
      </div>
    </div>
  );
}

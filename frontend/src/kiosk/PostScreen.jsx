export default function PostScreen({ post, postIndex, totalPosts, onSelect }) {
  return (
    <div className="kiosk-body">
      <div className="post-progress">POST {postIndex + 1} OF {totalPosts}</div>
      <div className="post-pill">{post.title}</div>

      <div className="candidate-grid">
        {post.candidates.map((c) => (
          <button
            key={c.id}
            className="candidate-tile"
            onClick={() => onSelect(c.id)}
          >
            <img src={`/symbols/${c.symbol_file}`} alt="" />
            <span className="candidate-name">{c.name}</span>
          </button>
        ))}

        <button className="candidate-tile nota-tile" onClick={() => onSelect(null)}>
          <span className="nota-mark">✕</span>
          <span className="candidate-name">NOTA</span>
        </button>
      </div>
    </div>
  );
}

'use client';

export default function LockedScreen({ errorMessage, onGesture }) {
  return (
    <div className="kiosk-body" style={{ position: 'relative' }}>
      <div className="gesture-zone" onClick={onGesture} aria-hidden="true" />
      <div className="locked-icon">🔒</div>
      <h1 className="school-name">Voting Locked</h1>
      <p className="status-line">
        {errorMessage || 'Please contact the Election Officer for your next vote.'}
      </p>
    </div>
  );
}

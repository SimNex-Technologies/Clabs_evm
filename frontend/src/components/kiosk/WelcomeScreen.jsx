'use client';

export default function WelcomeScreen({ onStart, onGesture, voterName }) {
  return (
    <div className="kiosk-body" style={{ position: 'relative' }}>
      <div className="gesture-zone" onClick={onGesture} aria-hidden="true" style={{ zIndex: 0 }} />
      <h1 className="school-name" style={{ position: 'relative' }}>
        {voterName ? `Welcome, ${voterName}!` : 'Bhashyam High School Elections'}
      </h1>
      <p className="election-name" style={{ position: 'relative' }}>
        {voterName
          ? 'Bhashyam High School Elections — press Start Voting to begin.'
          : 'The voting machine is ready. Press Start Voting to begin.'}
      </p>
      <button className="big-button green" style={{ position: 'relative' }} onClick={onStart}>
        START VOTING
      </button>
    </div>
  );
}

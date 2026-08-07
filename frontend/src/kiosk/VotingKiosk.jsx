import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { playBeep } from '../beep.js';
import LockedScreen from './LockedScreen.jsx';
import WelcomeScreen from './WelcomeScreen.jsx';
import PostScreen from './PostScreen.jsx';
import ReviewScreen from './ReviewScreen.jsx';
import ThankYouScreen from './ThankYouScreen.jsx';

const POLL_MS = 1500;
const THANKYOU_MS = 8000;

// Phases that poll /api/state to notice when the officer unlocks the machine.
const POLLING_PHASES = new Set(['loading', 'locked', 'welcome']);

export default function VotingKiosk() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState('loading');
  const [machineState, setMachineState] = useState(null);
  const [ballot, setBallot] = useState(null); // { ballot_id, posts }
  const [postIndex, setPostIndex] = useState(0);
  const [selections, setSelections] = useState({}); // post_id -> candidate_id | null
  const [errorMessage, setErrorMessage] = useState(null);
  const [castSerial, setCastSerial] = useState(null);

  const refreshState = useCallback(async () => {
    try {
      const s = await api.getState();
      setMachineState(s);
      setPhase((prev) => {
        if (!POLLING_PHASES.has(prev)) return prev;
        return s.status === 'UNLOCKED' ? 'welcome' : 'locked';
      });
    } catch {
      // backend still starting up - keep showing the loading/locked screen
    }
  }, []);

  useEffect(() => {
    refreshState();
    const id = setInterval(() => {
      if (POLLING_PHASES.has(phase)) refreshState();
    }, POLL_MS);
    return () => clearInterval(id);
  }, [phase, refreshState]);

  async function handleStartVoting() {
    try {
      const b = await api.getBallot();
      setBallot(b);
      setPostIndex(0);
      setSelections({});
      setPhase('voting');
    } catch (e) {
      setErrorMessage(e.message);
      setPhase('locked');
    }
  }

  function handleSelect(candidateId) {
    const post = ballot.posts[postIndex];
    const next = { ...selections, [post.id]: candidateId };
    setSelections(next);
    if (postIndex + 1 < ballot.posts.length) {
      setPostIndex(postIndex + 1);
    } else {
      setPhase('review');
    }
  }

  function handleChangePost(index) {
    setPostIndex(index);
    setPhase('voting');
  }

  async function handleCast() {
    setPhase('casting');
    try {
      const stringKeyed = {};
      for (const [postId, candId] of Object.entries(selections)) {
        stringKeyed[postId] = candId;
      }
      const result = await api.castBallot(ballot.ballot_id, stringKeyed);
      playBeep();
      setCastSerial(result.serial);
      setPhase('thankyou');
      setTimeout(() => {
        setBallot(null);
        setSelections({});
        setCastSerial(null);
        setPhase('loading');
      }, THANKYOU_MS);
    } catch (e) {
      setErrorMessage(
        e.status === 409
          ? 'This voting session ended before your vote was submitted. Please contact the election officer.'
          : e.message,
      );
      setBallot(null);
      setSelections({});
      setPhase('locked');
    }
  }

  // Tap the school name 5 times within 3 seconds to reach the officer console.
  // Deliberately not linked anywhere in the kiosk UI a student would see.
  const tapTimes = useRef([]);
  function handleSecretGesture() {
    const now = Date.now();
    tapTimes.current = [...tapTimes.current, now].filter((t) => now - t < 3000);
    if (tapTimes.current.length >= 5) {
      tapTimes.current = [];
      navigate('/admin');
    }
  }

  return (
    <div className="kiosk" onContextMenu={(e) => e.preventDefault()}>
      <div className="marquee-bar">
        <span>{' '.repeat(4)}&lt;&lt;&lt;&lt; C-LABS DIGITAL EVM &gt;&gt;&gt;&gt;{' '.repeat(8)}&lt;&lt;&lt;&lt; BHASHYAM HIGH SCHOOL ELECTIONS &gt;&gt;&gt;&gt;{' '.repeat(8)}</span>
      </div>

      {(phase === 'loading' || phase === 'locked') && (
        <LockedScreen errorMessage={errorMessage} onGesture={handleSecretGesture} />
      )}

      {phase === 'welcome' && (
        <WelcomeScreen onStart={handleStartVoting} onGesture={handleSecretGesture} />
      )}

      {phase === 'voting' && ballot && (
        <PostScreen
          post={ballot.posts[postIndex]}
          postIndex={postIndex}
          totalPosts={ballot.posts.length}
          onSelect={handleSelect}
        />
      )}

      {phase === 'review' && ballot && (
        <ReviewScreen
          posts={ballot.posts}
          selections={selections}
          onChange={handleChangePost}
          onCast={handleCast}
        />
      )}

      {phase === 'casting' && (
        <div className="kiosk-body">
          <p className="status-line">Submitting your vote…</p>
        </div>
      )}

      {phase === 'thankyou' && <ThankYouScreen serial={castSerial} />}
    </div>
  );
}

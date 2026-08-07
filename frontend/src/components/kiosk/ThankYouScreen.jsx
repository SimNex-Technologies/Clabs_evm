'use client';

export default function ThankYouScreen({ serial }) {
  return (
    <div className="kiosk-body">
      <div className="thankyou-icon">✅</div>
      <h1 className="school-name">Vote Submitted Successfully</h1>
      {serial && <p className="status-line">Vote ID #{String(serial).padStart(3, '0')}</p>}
      <p className="status-line">
        Thank You For Voting.<br />Please Call The Election Officer For The Next Vote.
      </p>
    </div>
  );
}

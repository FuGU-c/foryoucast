import { AlertCircle, ArrowRight, Check, LoaderCircle, RefreshCw, X } from 'lucide-react';
import type { CloudJob } from './types';
import './generation-status.css';

const stateLabels: Record<CloudJob['state'], string> = {
  queued: 'Briefing queued',
  writing: 'Writing your briefing',
  checking: 'Checking the sources',
  audio: 'Creating the audio',
  waiting_retry: 'Waiting to retry',
  ready: 'Briefing ready',
  failed: 'Briefing could not finish',
};

export function GenerationStatus({
  job,
  profileName,
  retrying = false,
  onClose,
  onRetry,
  onOpenPodcasts,
}: {
  job: CloudJob;
  profileName: string;
  retrying?: boolean;
  onClose: () => void;
  onRetry: () => void;
  onOpenPodcasts: () => void;
}) {
  const failed = job.state === 'failed';
  const ready = job.state === 'ready';
  const progress = Math.max(0, Math.min(100, Math.round(job.progress || 0)));

  return (
    <aside className="generation-status" role="status" aria-live="polite" aria-atomic="true">
      <div className={`generation-status-icon ${failed ? 'is-failed' : ready ? 'is-ready' : ''}`}>
        {failed ? <AlertCircle size={19} /> : ready ? <Check size={19} /> : <LoaderCircle className="generation-spinner" size={19} />}
      </div>
      <div className="generation-status-body">
        <div className="generation-status-heading">
          <div>
            <span className="generation-status-profile">{profileName}’s briefing</span>
            <h2>{retrying ? 'Retrying your briefing' : stateLabels[job.state]}</h2>
          </div>
          <button className="generation-status-close" type="button" aria-label="Close generation status" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {failed ? (
          <p className="generation-status-message">{job.error || 'Something interrupted this briefing. You can try again.'}</p>
        ) : ready ? (
          <p className="generation-status-message">Your briefing is saved in Podcasts.</p>
        ) : (
          <>
            <div className="generation-status-stage">
              <span>{job.stage || stateLabels[job.state]}</span>
              <span>{progress}%</span>
            </div>
            <div
              className="generation-progress-track"
              role="progressbar"
              aria-label={job.stage || stateLabels[job.state]}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
            >
              <span style={{ width: `${progress}%` }} />
            </div>
          </>
        )}

        {(ready || (failed && job.can_retry)) && (
          <div className="generation-status-actions">
            {ready
              ? <button type="button" onClick={onOpenPodcasts}>Open Podcasts <ArrowRight size={14} /></button>
              : <button type="button" disabled={retrying} onClick={onRetry}>
                  {retrying ? <LoaderCircle className="generation-spinner" size={14} /> : <RefreshCw size={14} />}
                  {retrying ? 'Retrying…' : 'Try again'}
                </button>}
          </div>
        )}
      </div>
    </aside>
  );
}

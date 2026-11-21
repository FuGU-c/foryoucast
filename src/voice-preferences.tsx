import { useEffect, useRef, useState } from 'react';
import { Check, Pause, Play, Search, Shuffle, Sparkles } from 'lucide-react';
import type { Profile } from './types';
import type { ProfileChange } from './live-preferences';
import { deviceVoices, voiceId } from './voices';
import './voice-library.css';

type Sample = {
  id: string;
  name: string;
  label?: string;
  language: string;
  accent?: string;
  description: string;
  preview_url: string;
};

type VoiceOption = {
  id: string;
  name: string;
  label: string;
  description: string;
  accent?: string;
  preview_url: string;
};

export function VoicePreferences({
  profile,
  onEdit,
  onPlans,
  onPreviewStart,
}: {
  profile: Profile;
  onEdit: (change: ProfileChange) => void;
  onPlans: () => void;
  onPreviewStart: () => void;
}) {
  const [view, setView] = useState<'device' | 'elevenlabs'>(profile.tts_provider || 'device');
  const [voices, setVoices] = useState(() => deviceVoices(profile.language));
  const [samples, setSamples] = useState<Sample[]>([]);
  const [samplesReady, setSamplesReady] = useState(false);
  const [samplesUnavailable, setSamplesUnavailable] = useState(false);
  const [playing, setPlaying] = useState('');
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const audio = useRef<HTMLAudioElement | null>(null);
  const speech = useRef<SpeechSynthesisUtterance | null>(null);
  const token = useRef(0);
  const key = view === 'device' ? 'device_voices' : 'elevenlabs_voices';
  const chosen = profile[key]?.[profile.language] || [];
  const options: VoiceOption[] = view === 'device'
    ? voices.map(voice => ({
        id: voiceId(voice),
        name: voice.name,
        label: voice.name,
        description: /microsoft/i.test(voice.name)
          ? 'Basic voice · lower-fidelity narration'
          : 'Basic voice',
        accent: voice.lang,
        preview_url: '',
      }))
    : samples
        .filter(voice => voice.language === profile.language)
        .map(voice => ({
          id: voice.id,
          name: voice.name,
          label: voice.label || voice.name,
          description: voice.description,
          accent: voice.accent,
          preview_url: voice.preview_url,
        }));
  const query = search.trim().toLocaleLowerCase();
  const visibleOptions = query
    ? options.filter(option => `${option.name} ${option.label} ${option.description} ${option.accent || ''}`.toLocaleLowerCase().includes(query))
    : options;

  function stop() {
    token.current++;
    audio.current?.pause();
    audio.current = null;
    if (speech.current) {
      window.speechSynthesis?.cancel();
      speech.current = null;
    }
    setPlaying('');
  }

  useEffect(() => {
    const refresh = () => setVoices(deviceVoices(profile.language));
    refresh();
    window.speechSynthesis?.addEventListener?.('voiceschanged', refresh);
    return () => window.speechSynthesis?.removeEventListener?.('voiceschanged', refresh);
  }, [profile.language]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/voice-samples.json', { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error('Voice sample list could not be loaded.');
        return response.json();
      })
      .then((data: Sample[]) => {
        setSamples(Array.isArray(data) ? data : []);
        setSamplesReady(true);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setSamplesUnavailable(true);
          setSamplesReady(true);
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    stop();
    setError('');
    setSearch('');
  }, [view, profile.language]);

  useEffect(() => () => {
    token.current++;
    audio.current?.pause();
    if (speech.current) window.speechSynthesis?.cancel();
  }, []);

  function select(id: string) {
    onEdit(current => {
      const ids = current[key]?.[current.language] || [];
      return {
        ...current,
        [key]: {
          ...current[key],
          [current.language]: ids.includes(id)
            ? ids.filter(value => value !== id)
            : ids.length < 2 ? [...ids, id] : ids,
        },
      };
    });
  }

  async function preview(option: VoiceOption) {
    if (playing === option.id) {
      stop();
      return;
    }
    stop();
    onPreviewStart();
    setError('');
    const request = token.current;
    setPlaying(option.id);
    const done = () => {
      if (request === token.current) setPlaying('');
    };

    if (view === 'elevenlabs') {
      const clip = new Audio(option.preview_url);
      audio.current = clip;
      clip.onended = done;
      clip.onerror = () => {
        if (request === token.current) {
          done();
          setError('This sample is unavailable right now. Try another voice.');
        }
      };
      try {
        await clip.play();
        if (request !== token.current) clip.pause();
      } catch {
        if (request === token.current) {
          done();
          setError('The sample could not play. Try again.');
        }
      }
      return;
    }

    const voice = voices.find(item => voiceId(item) === option.id);
    if (!voice) return;
    const line = {
      en: 'Good morning. Let’s make sense of today’s news, together.',
      de: 'Guten Morgen. Schauen wir gemeinsam auf die Nachrichten des Tages.',
      nl: 'Goedemorgen. Laten we samen het nieuws van vandaag bekijken.',
    }[profile.language];
    const utterance = new SpeechSynthesisUtterance(line);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.onend = done;
    utterance.onerror = done;
    speech.current = utterance;
    window.speechSynthesis.resume();
    window.speechSynthesis.speak(utterance);
  }

  const languageSampleCount = samples.filter(sample => sample.language === profile.language).length;

  return (
    <section className="voice-preferences">
      <div className="setting-section-heading">
        <span className="settings-kicker">THE VOICES OF YOUR DAY</span>
        <h3>Who would you like to hear?</h3>
        <p>Preview a voice and choose up to two for your podcasts. Leave the list empty and we’ll pick a language-matched pair.</p>
      </div>

      <div className="voice-library-tabs" aria-label="Voice library">
        <button aria-pressed={view === 'device'} onClick={() => setView('device')}>
          Basic voice<span>Free</span>
        </button>
        <button aria-pressed={view === 'elevenlabs'} onClick={() => setView('elevenlabs')}>
          Natural voice<span>Paid</span>
        </button>
      </div>

      <button
        className={`voice-auto ${!chosen.length ? 'chosen' : ''}`}
        aria-pressed={!chosen.length}
        onClick={() => onEdit(current => ({
          ...current,
          [key]: { ...current[key], [current.language]: [] },
        }))}
      >
        <Shuffle size={17} />
        <span><b>Surprise me</b><small>A fresh, language-matched pair for each episode</small></span>
        {!chosen.length && <Check size={16} />}
      </button>

      <label className="voice-search">
        <Search size={16} aria-hidden="true" />
        <input
          type="search"
          value={search}
          onChange={event => setSearch(event.target.value)}
          placeholder="Search voices or accents"
          aria-label="Search voices or accents"
        />
      </label>

      <div className="voice-sample-list" aria-label={view === 'device' ? 'Basic voices' : 'Natural voice samples'}>
        {visibleOptions.map(option => (
          <div className={`voice-sample ${chosen.includes(option.id) ? 'chosen' : ''}`} key={option.id}>
            <button
              className="voice-play"
              aria-label={`${playing === option.id ? 'Stop sample' : 'Preview voice'} ${option.name}`}
              aria-pressed={playing === option.id}
              onClick={() => void preview(option)}
            >
              {playing === option.id ? <Pause size={17} /> : <Play size={17} fill="currentColor" />}
            </button>
            <label className="voice-option-label">
              <span>
                <b>{option.label}</b>
                <small>{option.description}</small>
                {option.accent && <span className="voice-accent">{option.accent}</span>}
              </span>
              <input
                type="checkbox"
                aria-label={`Choose voice ${option.name}`}
                checked={chosen.includes(option.id)}
                disabled={!chosen.includes(option.id) && chosen.length >= 2}
                onChange={() => select(option.id)}
              />
            </label>
          </div>
        ))}
      </div>

      {!visibleOptions.length && (
        <p className="settings-inline-note">
          {view === 'device'
            ? options.length === 0
              ? 'No Basic voices are available for this language yet. Try another browser or add a voice in your device settings.'
              : 'No voices match your search.'
            : languageSampleCount === 0
              ? !samplesReady
                ? 'Loading voice samples…'
                : samplesUnavailable || samples.length === 0
                  ? 'Voice samples are unavailable right now. Device voices are still available.'
                  : 'No samples are available for this language right now.'
              : 'No voices match your search.'}
        </p>
      )}

      <p className="settings-inline-note">
        {view === 'device'
          ? 'Basic voices use your device’s speech service. Available voices vary by device.'
          : 'Sample clips from the ElevenLabs voice library. Live audio availability depends on account setup.'}
        {' '}{chosen.length ? `${chosen.length} of 2 selected.` : 'No selection needed.'}
      </p>

      {profile.tts_provider === view ? (
        <div className="active-voice-provider">
          <Check size={14} />{view === 'device' ? 'Using Basic voice' : 'Natural voice selected'}
        </div>
      ) : (
        <button
          className="voice-use-button"
          onClick={() => view === 'elevenlabs' && (!profile.plan || profile.plan === 'free')
            ? onPlans()
            : onEdit(current => ({ ...current, tts_provider: view }))}
        >
          <Sparkles size={15} />
          {view === 'device'
            ? 'Use Basic voice'
            : profile.plan === 'plus' || profile.plan === 'premium'
              ? 'Use Natural voice'
              : 'Explore natural voices'}
        </button>
      )}

      {error && <p className="settings-inline-note" role="status">{error}</p>}
    </section>
  );
}

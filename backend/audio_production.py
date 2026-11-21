"""Produce recorded chapters and one measured episode without changing the script.

No provider API calls happen here. Natural speech is supplied by the workflow;
basic speech uses the machine's installed System.Speech voices.
"""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
import wave

SAMPLE_RATE = 24000
PCM_BYTES_PER_SECOND = SAMPLE_RATE * 2
PAUSE_FRAMES = round(SAMPLE_RATE * .12)
MAX_AUDIO_BYTES = 80_000_000
CACHE_VERSION = 1


def _ffmpeg() -> str:
    configured = os.environ.get('FFMPEG_PATH')
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise RuntimeError('FFMPEG_PATH must name an existing ffmpeg executable')
        return str(path.resolve())
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        executable = shutil.which('ffmpeg')
        if executable:
            return executable
        raise RuntimeError('Recorded audio needs imageio-ffmpeg or FFMPEG_PATH') from None


def _run(arguments: list[str], *, timeout: int = 180) -> bytes:
    try:
        return subprocess.run(arguments, check=True, capture_output=True, timeout=timeout).stdout
    except subprocess.CalledProcessError as exc:
        # ffmpeg diagnostics can contain local paths, but never provider secrets.
        detail = exc.stderr.decode('utf-8', errors='replace')[-1200:]
        raise ValueError(f'Audio processing failed: {detail}') from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Audio processing timed out') from exc


def _decode_pcm(path: Path) -> bytes:
    pcm = _run([_ffmpeg(), '-nostdin', '-v', 'error', '-i', str(path),
                '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', str(SAMPLE_RATE),
                '-ac', '1', 'pipe:1'])
    if not pcm or len(pcm) % 2:
        raise ValueError('Audio did not decode to nonempty 24 kHz mono PCM')
    return pcm


def _encode(wav: Path, target: Path) -> None:
    _run([_ffmpeg(), '-nostdin', '-v', 'error', '-y', '-i', str(wav),
          '-map_metadata', '-1', '-ar', str(SAMPLE_RATE), '-ac', '1',
          '-codec:a', 'libmp3lame', '-b:a', '128k', '-write_xing', '1', str(target)])


def _root(media_root: Path) -> Path:
    root = Path(media_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _inside(root: Path, *parts: str) -> Path:
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Audio path must remain inside media/')
    return target


def _media_file(url: str, root: Path) -> Path:
    if not isinstance(url, str):
        raise ValueError('Chapter audio needs a local /media/ URL')
    parts = urlsplit(url)
    path = unquote(parts.path)
    if (parts.scheme or parts.netloc or parts.query or parts.fragment
            or not path.startswith('/media/') or '\\' in path or '\x00' in path
            or ':' in path):
        raise ValueError('Chapter audio needs a local /media/ URL')
    target = _inside(root, path[len('/media/'):])
    if not target.is_file() or target.suffix.lower() != '.mp3':
        raise ValueError('Chapter MP3 is missing')
    return target


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _turns(chapter: dict) -> list[dict]:
    turns = chapter.get('turns')
    if not isinstance(turns, list) or not turns:
        raise ValueError('Recorded chapters require approved dialogue turns')
    known = chapter.get('claim_source_ids')
    for turn in turns:
        if (not isinstance(turn, dict) or turn.get('speaker') not in {'maya', 'leo'}
                or not isinstance(turn.get('text'), str) or not turn['text'].strip()):
            raise ValueError('Each approved turn needs a Maya/Leo speaker and text')
        ids = turn.get('source_ids')
        if not isinstance(ids, list) or any(not isinstance(item, str) or not item for item in ids):
            raise ValueError('Each approved turn needs a source_ids array')
        if isinstance(known, list) and not set(ids).issubset(known):
            raise ValueError('A turn refers to a source outside the approved chapter')
    return copy.deepcopy(turns)


def _cache_paths(root: Path, cache_key: str, identity: dict) -> tuple[Path, Path]:
    if not isinstance(cache_key, str) or not cache_key.strip() or len(cache_key) > 4096:
        raise ValueError('A nonempty chapter cache key is required')
    folder = _inside(root, 'chapter-cache')
    folder.mkdir(parents=True, exist_ok=True)
    name = _digest({'version': CACHE_VERSION, 'key': cache_key, **identity})
    return _inside(root, 'chapter-cache', name + '.mp3'), _inside(root, 'chapter-cache', name + '.json')


def _atomic_json(path: Path, value: dict) -> None:
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     suffix='.json', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _cached(path: Path, metadata: Path) -> dict | None:
    try:
        data = json.loads(metadata.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('sha256') != _file_hash(path):
            return None
        data['duration_seconds'] = len(_decode_pcm(path)) / PCM_BYTES_PER_SECOND
        data.pop('sha256', None)
        # Derive the URL from our validated path, never from cached JSON.
        data['url'] = '/media/chapter-cache/' + path.name
        return data
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _save_metadata(path: Path, metadata: Path, data: dict) -> dict:
    data = copy.deepcopy(data)
    data['url'] = '/media/chapter-cache/' + path.name
    _atomic_json(metadata, {**data, 'sha256': _file_hash(path)})
    return data


def _sapi_render(turns: list[dict], language: str, directory: Path) -> list[dict]:
    """Pass all user text as JSON data to a fixed, saved PowerShell script."""
    request = directory / 'input.json'
    response = directory / 'result.json'
    request.write_text(json.dumps({'language': language, 'turns': turns,
                                   'output_directory': str(directory),
                                   'result_path': str(response)}, ensure_ascii=False), encoding='utf-8')
    helper = Path(__file__).with_name('render_sapi.ps1')
    # The modern runtime sees installed OneCore voices as well as Desktop voices.
    powershell = shutil.which('pwsh') or shutil.which('powershell.exe')
    if not powershell:
        raise RuntimeError('Basic recorded audio requires PowerShell and System.Speech')
    _run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
          '-File', str(helper), '-InputPath', str(request)], timeout=600)
    result = json.loads(response.read_text(encoding='utf-8-sig'))
    rendered = result.get('turns')
    if not isinstance(rendered, list) or len(rendered) != len(turns):
        raise ValueError('System.Speech did not render every approved turn')
    return rendered


def render_basic_chapter(chapter: dict, language: str, media_root: Path, cache_key: str) -> dict:
    turns = _turns(chapter)
    if not isinstance(language, str) or not re.fullmatch(r'[a-z]{2}(?:-[A-Za-z]{2})?', language):
        raise ValueError('Speech language must be a language code such as en, nl or de')
    root = _root(media_root)
    path, metadata = _cache_paths(root, cache_key, {'provider': 'microsoft-sapi',
                                                  'language': language, 'turns': turns})
    cached = _cached(path, metadata)
    if cached:
        return cached
    with tempfile.TemporaryDirectory(prefix='sapi-', dir=path.parent) as temporary:
        directory = Path(temporary).resolve()
        rendered = _sapi_render(turns, language, directory)
        wav_path = directory / 'chapter.wav'
        frames = 0
        alignment = []
        with wave.open(str(wav_path), 'wb') as output:
            output.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            for index, (turn, item) in enumerate(zip(turns, rendered, strict=True)):
                filename = item.get('file')
                if not isinstance(filename, str) or Path(filename).name != filename:
                    raise ValueError('System.Speech returned an unsafe audio path')
                source = _inside(directory, filename)
                voice = item.get('voice_id')
                if not source.is_file() or not isinstance(voice, str) or not voice:
                    raise ValueError('System.Speech returned an incomplete audio turn')
                pcm = _decode_pcm(source)
                start = frames / SAMPLE_RATE
                output.writeframesraw(pcm)
                frames += len(pcm) // 2
                alignment.append({**turn, 'voice_id': voice, 'start_seconds': start,
                                  'end_seconds': frames / SAMPLE_RATE})
                if index < len(turns) - 1:
                    output.writeframesraw(b'\0\0' * PAUSE_FRAMES)
                    frames += PAUSE_FRAMES
        encoded = directory / 'chapter.mp3'
        _encode(wav_path, encoded)
        duration = len(_decode_pcm(encoded)) / PCM_BYTES_PER_SECOND
        os.replace(encoded, path)
    return _save_metadata(path, metadata, {
        'duration_seconds': duration, 'provider': 'microsoft-sapi',
        'voice_ids': list(dict.fromkeys(item['voice_id'] for item in alignment)),
        'alignment': {'turns': alignment, 'timing_basis': 'measured-turn-audio'},
    })


def _number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _without_space(text: str) -> str:
    return ''.join(text.split())


def _natural_alignment(result: dict, turns: list[dict], duration: float) -> tuple[dict, list[dict]]:
    alignment = result.get('alignment') or result.get('normalized_alignment')
    if not isinstance(alignment, dict):
        raise ValueError('Natural speech requires character alignment')
    characters = alignment.get('characters')
    starts = alignment.get('character_start_times_seconds')
    ends = alignment.get('character_end_times_seconds')
    if (not isinstance(characters, list) or not characters
            or any(not isinstance(char, str) or len(char) != 1 for char in characters)
            or not isinstance(starts, list) or not isinstance(ends, list)
            or len(starts) != len(characters) or len(ends) != len(characters)):
        raise ValueError('Natural character alignment arrays must have matching lengths')
    spoken = ''.join(characters)
    if _without_space(spoken) != _without_space(''.join(turn['text'] for turn in turns)):
        raise ValueError('Natural alignment does not cover the complete approved script')
    previous_start = previous_end = 0.0
    for start, end in zip(starts, ends, strict=True):
        start = _number(start, 'Character start')
        end = _number(end, 'Character end')
        if start < previous_start or end < previous_end or end < start or start < 0 or end > duration + .15:
            raise ValueError('Natural character alignment is outside the audio or out of order')
        previous_start, previous_end = start, end
    segments = result.get('voice_segments')
    if not isinstance(segments, list) or not segments:
        raise ValueError('Natural dialogue requires voice_segments')
    previous_start = previous_end = 0.0
    previous_character_end = 0
    covered_text = ['' for _ in turns]
    speaker_voices = {}
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get('voice_id'), str) or not segment['voice_id']:
            raise ValueError('Each natural voice segment requires a voice_id')
        start = _number(segment.get('start_time_seconds', segment.get('start_seconds')), 'Voice segment start')
        end = _number(segment.get('end_time_seconds', segment.get('end_seconds')), 'Voice segment end')
        if start < previous_start or end < previous_end or start < 0 or end <= start or end > duration + .15:
            raise ValueError('Natural voice segment is outside the audio or out of order')
        previous_start, previous_end = start, end
        if 'speaker_index' in segment and (type(segment['speaker_index']) is not int or segment['speaker_index'] not in (0, 1)):
            raise ValueError('Natural speaker_index must identify Maya or Leo')
        lower, upper = segment.get('character_start_index'), segment.get('character_end_index')
        if type(lower) is not int or type(upper) is not int or not previous_character_end <= lower < upper <= len(characters):
            raise ValueError('Natural voice segment character range is invalid')
        if _without_space(''.join(characters[previous_character_end:lower])):
            raise ValueError('Natural voice segments leave approved words uncovered')
        if start > starts[lower] + .15 or end < ends[upper - 1] - .15:
            raise ValueError('Natural voice segment does not cover its character timing')
        previous_character_end = upper
        turn_index = segment.get('dialogue_input_index')
        if type(turn_index) is not int or not 0 <= turn_index < len(turns):
            raise ValueError('Natural voice segment needs a valid dialogue_input_index')
        covered_text[turn_index] += ''.join(characters[lower:upper])
        speaker = turns[turn_index]['speaker']
        if speaker in speaker_voices and speaker_voices[speaker] != segment['voice_id']:
            raise ValueError('Natural dialogue changes voice within the same approved speaker')
        speaker_voices[speaker] = segment['voice_id']
    if (_without_space(''.join(characters[previous_character_end:]))
            or any(_without_space(text) != _without_space(turn['text'])
                   for text, turn in zip(covered_text, turns, strict=True))):
        raise ValueError('Natural voice segments do not cover every complete approved turn')
    if len(speaker_voices) != len(set(speaker_voices.values())):
        raise ValueError('Natural Maya and Leo dialogue requires two distinct voices')
    return copy.deepcopy(alignment), copy.deepcopy(segments)


def persist_natural_chapter(chapter: dict, result: dict, media_root: Path, cache_key: str) -> dict:
    turns = _turns(chapter)
    if not isinstance(result, dict):
        raise ValueError('Natural speech response must be an object')
    encoded = result.get('audio_base64')
    if not isinstance(encoded, str) or not encoded or len(encoded) > (MAX_AUDIO_BYTES * 4 // 3 + 4):
        raise ValueError('Natural speech needs a bounded nonempty audio_base64 string')
    try:
        audio = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError('Natural audio_base64 is invalid') from exc
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise ValueError('Natural speech audio is empty or too large')
    # Decode first, then validate timing against actual audio before publishing it.
    root = _root(media_root)
    identity = {'provider': 'elevenlabs', 'turns': turns,
                'audio_sha256': hashlib.sha256(audio).hexdigest()}
    path, metadata = _cache_paths(root, cache_key, identity)
    with tempfile.TemporaryDirectory(prefix='natural-', dir=path.parent) as temporary:
        candidate = Path(temporary) / 'chapter.mp3'
        candidate.write_bytes(audio)
        # Accept MP3 responses only, even when ffmpeg can decode a different format.
        if not (audio.startswith(b'ID3') or (len(audio) > 1 and audio[0] == 0xff and audio[1] & 0xe0 == 0xe0)):
            raise ValueError('Natural speech response must contain MP3 audio')
        duration = len(_decode_pcm(candidate)) / PCM_BYTES_PER_SECOND
        alignment, segments = _natural_alignment(result, turns, duration)
        os.replace(candidate, path)
    return _save_metadata(path, metadata, {
        'duration_seconds': duration, 'provider': 'elevenlabs',
        'alignment': alignment, 'voice_segments': segments,
        'voice_ids': list(dict.fromkeys(segment['voice_id'] for segment in segments)),
    })


def combine_episode(edition: dict, media_root: Path) -> dict:
    """Decode complete chapters, concatenate PCM, encode one seekable episode.

    Timings use sample counts, with no speed adjustment, target duration, or
    transcript truncation. The final duration is measured from the encoded MP3.
    """
    if not isinstance(edition, dict) or not isinstance(edition.get('chapters'), list) or not edition['chapters']:
        raise ValueError('An episode needs at least one recorded chapter')
    root = _root(media_root)
    folder = _inside(root, 'episodes')
    folder.mkdir(parents=True, exist_ok=True)
    output = copy.deepcopy(edition)
    frames = 0
    providers = set()
    voices = []
    with tempfile.TemporaryDirectory(prefix='assembly-', dir=folder) as temporary:
        directory = Path(temporary)
        wav_path = directory / 'episode.wav'
        with wave.open(str(wav_path), 'wb') as wav:
            wav.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            for chapter in output['chapters']:
                audio = chapter.get('audio')
                if not isinstance(audio, dict):
                    raise ValueError('Every chapter must have recorded audio before assembly')
                path = _media_file(audio.get('url'), root)
                pcm = _decode_pcm(path)
                duration = len(pcm) / PCM_BYTES_PER_SECOND
                chapter['start_seconds'] = frames / SAMPLE_RATE
                wav.writeframesraw(pcm)
                frames += len(pcm) // 2
                chapter['end_seconds'] = frames / SAMPLE_RATE
                chapter['estimated_seconds'] = duration
                audio['duration_seconds'] = duration
                providers.add(audio.get('provider', 'unknown'))
                for voice in audio.get('voice_ids', []):
                    if isinstance(voice, str) and voice and voice not in voices:
                        voices.append(voice)
        encoded = directory / 'episode.mp3'
        _encode(wav_path, encoded)
        duration = len(_decode_pcm(encoded)) / PCM_BYTES_PER_SECOND
        if abs(duration - frames / SAMPLE_RATE) > .1:
            raise ValueError('Encoded episode timing differs from the concatenated chapters')
        filename = _file_hash(encoded) + '.mp3'
        target = _inside(root, 'episodes', filename)
        os.replace(encoded, target)
    output['chapters'][-1]['end_seconds'] = duration
    provider = next(iter(providers)) if len(providers) == 1 else 'mixed'
    mode = 'elevenlabs' if providers == {'elevenlabs'} else 'basic-audio' if providers == {'microsoft-sapi'} else 'mixed-audio'
    output.update({'episode_audio': {
        'url': '/media/episodes/' + filename, 'duration_seconds': duration,
        'provider': provider, 'voice_ids': voices, 'timing_basis': 'measured',
        'timing_provenance': '24 kHz mono decoded PCM sample counts; one MP3; no time scaling',
    }, 'duration_seconds': duration, 'estimated_seconds': duration, 'audio_mode': mode})
    if voices:
        output['voice_ids'] = voices
    return output

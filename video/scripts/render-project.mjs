import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {selectComposition, renderMedia, renderStill} from '@remotion/renderer';
import {enableTailwind} from '@remotion/tailwind-v4';

const [projectPath, stagePath, mode = 'render', value = '2'] = process.argv.slice(2);
const project = path.resolve(projectPath);
const stage = path.resolve(stagePath);
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
fs.mkdirSync(stage, {recursive: true});
try {
  const serveUrl = await bundle({
    entryPoint: path.join(project, 'index.tsx'),
    rootDir,
    publicDir: path.join(project, 'public'),
    outDir: path.join(stage, 'bundle'),
    webpackOverride: enableTailwind,
  });
  const composition = await selectComposition({serveUrl, id: 'Reel', timeoutInMilliseconds: 120000});
  fs.writeFileSync(path.join(stage, 'composition.json'), JSON.stringify(composition, null, 2));
  const common = {serveUrl, composition, timeoutInMilliseconds: 120000, logLevel: 'error',
    offthreadVideoCacheSizeInBytes: 512 * 1024 * 1024};
  if (mode === 'still') {
    const frame = Number(value);
    if (!Number.isInteger(frame) || frame < 0 || frame >= composition.durationInFrames) {
      throw new Error('Still frame is outside the composition');
    }
    await renderStill({...common, frame, output: path.join(stage, 'frame.png')});
  } else if (mode === 'preview') {
    const concurrency = Number(value);
    if (!Number.isInteger(concurrency) || concurrency < 1) throw new Error('Invalid concurrency');
    await renderMedia({...common, codec: 'h264', scale: 0.5, concurrency,
      enforceAudioTrack: true, outputLocation: path.join(stage, 'preview.mp4')});
    console.log('Draft preview complete');
  } else {
    const concurrency = Number(value);
    if (!Number.isInteger(concurrency) || concurrency < 1) throw new Error('Invalid concurrency');
    const parts = [];
    for (let start = 0; start < composition.durationInFrames; start += 800) {
      const end = Math.min(start + 799, composition.durationInFrames - 1);
      const name = `part-${parts.length}.mp4`;
      await renderMedia({...common, codec: 'h264', muted: true, concurrency,
        frameRange: [start, end], outputLocation: path.join(stage, name)});
      parts.push(name);
      console.log(`Picture ${end + 1}/${composition.durationInFrames}`);
    }
    fs.writeFileSync(path.join(stage, 'parts.txt'), parts.map(p => `file '${p}'`).join('\n'));
    await renderMedia({...common, codec: 'wav', concurrency: Math.min(2, concurrency),
      enforceAudioTrack: true, sampleRate: 48000, outputLocation: path.join(stage, 'sound.wav')});
    console.log('Lossless audio complete');
  }
} catch (error) {
  console.error(error.stack ?? error);
  process.exitCode = 1;
}

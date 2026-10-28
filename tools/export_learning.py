"""Render lesson frames with pygame and encode verified looping GIFs with Pillow.

Use --render with the game interpreter and --encode with a Pillow interpreter,
or --all when both optional packages are available in one environment.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
NAMES = ("01_greedy", "02_rules", "03_blinky", "04_pinky", "05_inky", "06_clyde", "07_modes")
POSTER_FRAMES = (300, 270, 180, 180, 120, 30, 360)


def render(output: Path, scale: int = 3):
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame
    from pacman.learning import LESSONS, LOOP_FRAMES, LearningPlayer
    from pacman.video import Renderer, SCREEN

    output.mkdir(parents=True, exist_ok=True)
    pygame.init()
    pygame.display.set_mode(SCREEN)
    renderer = Renderer()
    player = LearningPlayer()
    manifest = {"frame_duration_ms": 100, "loop_duration_ms": 8000, "lessons": []}
    try:
        for index, name in enumerate(NAMES):
            folder = output / "frames" / name
            folder.mkdir(parents=True, exist_ok=True)
            player.select(index)
            player.details_open = False
            for number, frame in enumerate(range(0, LOOP_FRAMES, 6)):
                player.elapsed = frame
                surface = renderer.draw_learning(player)
                image = pygame.transform.scale(surface, (SCREEN[0] * scale, SCREEN[1] * scale))
                pygame.image.save(image, str(folder / f"{number:03d}.png"))
            player.elapsed = POSTER_FRAMES[index]
            pygame.image.save(pygame.transform.scale(renderer.draw_learning(player),
                              (SCREEN[0] * scale, SCREEN[1] * scale)), str(output / f"{name}.png"))
            manifest["lessons"].append({"file": f"{name}.gif", "title": LESSONS[index].title,
                                         "frames": 80, "folder": f"frames/{name}"})
            print(f"Rendered {name}: 80 frames", flush=True)
        player.select(4)
        player.details_open = True
        pygame.image.save(pygame.transform.scale(renderer.draw_learning(player),
                          (SCREEN[0] * scale, SCREEN[1] * scale)), str(output / "05_inky_details.png"))
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        pygame.quit()


def encode(output: Path, cleanup: bool = False):
    from PIL import Image, ImageChops

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for lesson in manifest["lessons"]:
        paths = sorted((output / lesson["folder"]).glob("*.png"))
        if len(paths) != lesson["frames"]:
            raise ValueError(f"Incomplete frame set: {lesson['file']}")
        colors = set()
        for path in paths:
            with Image.open(path) as source:
                entries = source.convert("RGB").getcolors(256)
                if entries is None:
                    raise ValueError("Lesson palette unexpectedly exceeds 256 colors")
                colors.update(color for count, color in entries)
        if len(colors) > 256:
            raise ValueError("Combined lesson palette exceeds 256 colors")
        ordered = sorted(colors)
        palette = Image.new("P", (1, 1))
        values = [value for color in ordered for value in color]
        palette.putpalette(values + [0] * (768 - len(values)))
        frames = []
        for path in paths:
            with Image.open(path) as source:
                frames.append(source.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE))
        destination = output / lesson["file"]
        frames[0].save(destination, save_all=True, append_images=frames[1:],
                       duration=manifest["frame_duration_ms"], loop=0, disposal=2,
                       optimize=False, background=ordered.index((0, 0, 0)))
        with Image.open(destination) as gif:
            if not gif.is_animated or gif.info.get("loop") != 0:
                raise AssertionError(f"GIF does not animate and loop: {destination}")
            duration = 0
            for frame in range(gif.n_frames):
                gif.seek(frame)
                duration += gif.info.get("duration", 0)
            if duration != manifest["loop_duration_ms"]:
                raise AssertionError(f"Unexpected GIF duration: {duration}")
            # Check actual decoded frames against the source at each timestamp.
            gif.seek(0)
            current_end = gif.info.get("duration", 0)
            decoded_index = 0
            for index in (0, 20, 40, 60, 79):
                timestamp = index * manifest["frame_duration_ms"]
                while timestamp >= current_end and decoded_index + 1 < gif.n_frames:
                    decoded_index += 1
                    gif.seek(decoded_index)
                    current_end += gif.info.get("duration", 0)
                with Image.open(paths[index]) as expected:
                    if ImageChops.difference(gif.convert("RGB"), expected.convert("RGB")).getbbox():
                        raise AssertionError(f"Decoded GIF differs from source at frame {index}: {destination}")
            lesson["decoded_frames"] = gif.n_frames
            lesson["duration_ms"] = duration
        for frame in frames:
            frame.close()
        lesson["bytes"] = destination.stat().st_size
        print(f"Verified {destination.name}: {lesson['decoded_frames']} frames, {duration} ms", flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if cleanup:
        scratch = (output / "frames").resolve()
        if scratch.name != "frames" or not scratch.is_relative_to(ROOT.resolve()):
            raise ValueError("Refusing to clean frame directories outside this project")
        shutil.rmtree(scratch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--render", action="store_true")
    mode.add_argument("--encode", action="store_true")
    mode.add_argument("--all", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "learning")
    parser.add_argument("--cleanup", action="store_true", help="remove verified intermediate PNG frames")
    options = parser.parse_args()
    if options.render or options.all:
        render(options.output)
    if options.encode or options.all:
        encode(options.output, options.cleanup)


if __name__ == "__main__":
    main()

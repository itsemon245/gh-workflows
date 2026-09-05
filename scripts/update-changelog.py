#!/usr/bin/env python3
import argparse
import datetime as dt
import pathlib
import subprocess


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def previous_tag(ref: str) -> str | None:
    commit = git("rev-parse", ref)
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", f"{commit}^"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def latest_tag() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def release_commits(ref: str, prior_tag: str | None) -> list[str]:
    commit = git("rev-parse", ref)
    revision_range = f"{prior_tag}..{commit}" if prior_tag else commit
    output = git("log", "--no-merges", "--format=- %s (%h)", revision_range)
    return [line for line in output.splitlines() if line.strip()]


def render_notes(tag: str, prior_tag: str | None, commits: list[str]) -> str:
    today = dt.datetime.now(dt.UTC).date().isoformat()
    intro = f"Changes since `{prior_tag}`." if prior_tag else "Initial release."
    body = "\n".join(commits) if commits else "- No changes recorded."
    return f"## {tag} - {today}\n\n_{intro}_\n\n{body}\n"


def update_changelog(changelog: pathlib.Path, tag: str, notes: str) -> None:
    title = "# Changelog\n\n"
    existing = changelog.read_text(encoding="utf-8") if changelog.exists() else title
    if not existing.startswith("# Changelog"):
        existing = title + existing

    lines = existing.splitlines()
    output: list[str] = []
    skip = False
    target_heading = f"## {tag} - "

    for line in lines:
        if line.startswith(target_heading):
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            output.append(line)

    cleaned = "\n".join(output).strip()
    if cleaned == "# Changelog":
        updated = f"{cleaned}\n\n{notes}"
    else:
        updated = f"# Changelog\n\n{notes}\n{cleaned.removeprefix('# Changelog').strip()}\n"

    changelog.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate release notes and update CHANGELOG.md.")
    parser.add_argument("tag", help="Release tag, for example v0.1.0")
    parser.add_argument(
        "--ref",
        default=None,
        help="Git ref to summarize. Defaults to the tag if it exists, otherwise HEAD.",
    )
    parser.add_argument("--changelog", default="CHANGELOG.md", help="Changelog file to update")
    parser.add_argument("--notes", default="release-notes.md", help="Release notes output file")
    args = parser.parse_args()

    ref = args.ref
    if ref is None:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{args.tag}^{{}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        ref = f"{args.tag}^{{}}" if result.returncode == 0 else "HEAD"

    prior_tag = latest_tag() if ref == "HEAD" else previous_tag(ref)
    commits = release_commits(ref, prior_tag)
    notes = render_notes(args.tag, prior_tag, commits)

    pathlib.Path(args.notes).write_text(notes, encoding="utf-8")
    update_changelog(pathlib.Path(args.changelog), args.tag, notes)


if __name__ == "__main__":
    main()

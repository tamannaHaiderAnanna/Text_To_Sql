"""Pack everything Colab needs into one zip: the scripts, one database's SchemaShift files and
the results so far (so runs that are already finished are skipped on Colab).

Usage (from the project folder):
    .venv\\Scripts\\python.exe -I scripts\\make_colab_zip.py data\\schemashift\\student_club ..\\colab\\schemashift_student_club.zip
"""
import sys
import zipfile
from pathlib import Path

SCRIPTS = ("run_models.py", "make_schema_changes.py", "compare_results.py")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: make_colab_zip.py <task folder> <zip file>")
    project = Path(__file__).resolve().parent.parent
    task_dir, zip_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    files = [project / "scripts" / s for s in SCRIPTS] + [project / "requirements.txt"]
    files += sorted(p for p in task_dir.iterdir() if p.is_file())
    files += sorted(p for p in (project / "results").glob("*") if p.is_file())
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(project).as_posix())
    print(f"{zip_path}: {len(files)} files, {zip_path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

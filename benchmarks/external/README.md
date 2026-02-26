# External Benchmark Corpus

A curated set of publicly available LaTeX documents from .edu sites,
used to benchmark altex's PDF/UA tagging across diverse document types.

## Sources

All files are downloaded from public university web pages. No login
is required to access any of these files.

| ID | Category | Institution | Source |
|----|----------|-------------|--------|
| wm-thesis | Academic paper | William & Mary | [jxshix.people.wm.edu](https://jxshix.people.wm.edu/LaTeX-tutorial.html) |
| tufts-beamer | Beamer slides | Tufts University | [gmcninch.math.tufts.edu](https://gmcninch.math.tufts.edu/2024-Sp-Math190/course-assets/latex-examples/beamer-example.pdf) |
| duke-cv | CV/Resume | Duke University | [sites.math.duke.edu](https://sites.math.duke.edu/computing/tex/templates.html) |
| utoledo-syllabus | Course syllabus | University of Toledo | [utoledo.edu](https://www.utoledo.edu/nsm/mathstats/syllabus-templates.html) |
| duke-exam | Exam | Duke University | [sites.math.duke.edu](https://sites.math.duke.edu/computing/tex/templates.html) |
| bu-homework | Homework solution | Boston University | [cs-people.bu.edu](https://cs-people.bu.edu/januario/teaching/cs237/sample-hw-solution.tex) |
| uw-homework | Homework assignment | University of Washington | [faculty.washington.edu](https://faculty.washington.edu/rjl/fdmbook/latex/) |

## Notes

- The Duke files (CV, exam) were originally distributed as PostScript
  (.ps). PDFs were generated via `ps2pdf`.
- The Duke exam template depends on `testpoints.tex` (included as
  `duke-exam-testpoints.tex`), but the compiled PDF is self-contained.
- The W&M thesis references external image files not included here;
  only the .tex source and compiled .pdf are provided.
- See `manifest.json` for full metadata including source URLs and
  notable LaTeX features exercised by each document.

## Usage

These files are used by `scripts/benchmark_report.py` when the
`benchmarks/external/` directory exists. They appear as a separate
"External Corpus" section in the benchmark report.

```bash
python3 scripts/benchmark_report.py --tag-first
```

## License

These files are educational materials shared publicly by their
respective universities for teaching purposes. They are used here
solely for accessibility testing and benchmarking.

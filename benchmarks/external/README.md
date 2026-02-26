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
| stanford-beamer | Beamer slides | Stanford University | [github.com/sanhacheong](https://github.com/sanhacheong/stanford-beamer-presentation) |
| ucdavis-beamer | Beamer slides | UC Davis | [heather.cs.ucdavis.edu](https://heather.cs.ucdavis.edu/matloff/public_html/beamer.html) |
| metropolis-demo | Beamer slides | CTAN / GitHub | [github.com/matze/mtheme](https://github.com/matze/mtheme) |
| ucsd-math184a-hw | Homework | UC San Diego | [cseweb.ucsd.edu/~dakane](https://cseweb.ucsd.edu/~dakane/Math184A/) |
| ucsd-math184a-hw5 | Homework | UC San Diego | [cseweb.ucsd.edu/~dakane](https://cseweb.ucsd.edu/~dakane/Math184A/) |
| upenn-cs446-hw | Homework (ML) | University of Pennsylvania | [cis.upenn.edu/~danroth](https://www.cis.upenn.edu/~danroth/Teaching/CS446-17/homework.html) |
| jdavis-hw-template | Homework template | GitHub (jdavis) | [github.com/jdavis](https://github.com/jdavis/latex-homework-template) |
| sfsu-csc746-hw | Homework (HPC) | San Francisco State | [github.com/SFSU-Bethel](https://github.com/SFSU-Bethel-Instructional/CSC_746_HomeworkTemplate) |
| cambridge-dist-sys | Lecture notes | University of Cambridge | [github.com/ept/dist-sys](https://github.com/ept/dist-sys) |
| elegantpaper-en | Paper template | GitHub (ElegantLaTeX) | [github.com/ElegantLaTeX](https://github.com/ElegantLaTeX/ElegantPaper) |

## Notes

- The Duke files (CV, exam) were originally distributed as PostScript
  (.ps). PDFs were generated via `ps2pdf`.
- The Duke exam template depends on `testpoints.tex` (included as
  `duke-exam-testpoints.tex`), but the compiled PDF is self-contained.
- The W&M thesis references external image files not included here;
  only the .tex source and compiled .pdf are provided.
- The Stanford Beamer slides reference custom `.sty` theme files and
  images not included here; the compiled PDF is self-contained.
- The Cambridge distributed systems notes reference `setup.tex` and
  images not included; the compiled PDF is from the course website.
- The UPenn CS446 homework references an external `cs446.tex` macro
  file not included here.
- The ElegantPaper template uses a custom `elegantpaper.cls` not
  included here.
- The Metropolis demo PDF is from the CTAN mirror; the `.tex` source
  is from the GitHub repository.
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

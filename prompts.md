# Prompts

## Prompt 1

I would like to create a very simple proof-of-concept app that post-processes a PDF document created with latex and then embeds alt-text to make the document more accessible. Please use standard tools. Please make this tool as simple as possible as a proof of concept. Err for less code, err for using standard libraries and common libraries, even if it requires implementing basic shims and abstractions. Do not push to github. Do not make commits. Create context documents for yourself and documents that encode these instructions and best practices. Always ask me to review your plans before executing.

## Prompt 2

I have added my example resume as a latex document to start with

## Prompt 3

Thanks, I added some feedback at the beginning. Please review my feedback and revise your plan.

## Prompt 4

Great, let's do it. Optimize for modularity, clarity of reading the code, and simplicity. Isolate components through well-defined interfaces. Minimize sharing of "context" type data structures and grab-bag maps, etc. Please make this code as easy to review as possible. I've also included an old copy of a theory of computation course with many latex source documents and exams that can be used as test cases. Please spend a few minutes reviewing the examples and content to see if there's anything that can be used as test cases for you.

## Prompt 5

Can you please generate some demo scripts that run the pipeline and allow me to demonstrate the effectiveness?

## Prompt 6

In the demo directory, I attached the report from the adobe accessibility tool. Please evaluate the output, use the internet and adobe's documentation to determine next steps, and create an implementation plan for how to address some of the findings.

## Prompt 7

Ok, I added feedback to the implementation plan. Please take a look.

## Prompt 8

Perfect, let's move ahead with the plan. One change: update the demos to include a variant with the font fix so that I can evaluate the output.

## Prompt 9

Ok, let's turn this into a web tool. Let's create a frontend to invoke the pipeline via a web interface. The user should be able to update their latex source document and pdf, then download an annotated PDF. The accessibility output should be part of the web-based output. Build this into a docker container that can run and expose a port. Create the frontend by creating a service for the pipeline, then a very simple web frontend that is a client to the service. Both components should be packaged into the docker container. Provide instructions for running locally, including scripts to start a webserver to serve the frontend to run the python service. Create an implementation plan before beginning and allow me to review.

## Prompt 10

Let's do it. Please continue with our best practices of keeping it simple, minimizing information sharing, and writing tight, concise code.

## Prompt 11

Please update the project documentation and update the gitignore to exclude demo outputs.

## Prompt 12

ok, let's quit our session. Let's make sure that this is ready to hand off to another session or LLM. Please add all agent-handoff instructions to elements of the project that are needed or will require documentation for another agent to pick up your work.

## Prompt 13

Please emit all of my prompts to a file named prompts.md

## Prompt 14

An opencode session was modifying the project to add support for math to speech by shelling out to a node SRE. It was also planning on implementing an embedded alternate document feature as a fallback. Let's have you pick up this work. Please revert the current changes and give me an implementation plan for adding support for math-to-speech (provide me a few options) and for embedding the entire document as html or markdown in order to give the user a fallback option on complex documents

## Prompt 15

Ok, I have added my feedback to your plan. Please review my feedback and follow my instructions to update the plan and provide answers to my questions. Afterward, allow me to re-review the plan and provide final implementation shaping before you begin code changes.

## Prompt 16

Perfect. Please add the plan to the docs/ directory with a name that corresponds to the features we're implementing. Then begin implementation. Please create appropriate demo pipelines.

## Prompt 17

Please create a Makefile to install dependencies, run common commands, build the docker container, and build the project for running local. Also include a clean target that cleans up demo output. Also make sure that you append our prompts to the prompts.md file. Update any necessary documents as well.

## Prompt 18

This project is a pipeline tool to make accessible PDFs given their source latex material. I would like for you to audit this code against other tools, including verapdf, which I have just installed on this system. Please build benchmarks that test our tool against verapdf. Documentation for the project is available here (https://verapdf.org/software/) and their github repository is https://verapdf.org/software/. Please determine if there are any elements of the verapdf pipeline that we should be leveraging in this project, but I would also like for you to verify the reputation of verapdf via an internet search and search of the accessibility literature. Our benchmarks should run our pdfs through verapdf and validate use the output to improve our system. There are alternative tools that I would also like for you to explore, like pave pdf (https://pave-pdf.org/), which looks like it uses ML to provide heuristic matching. But, please do not hyper-optimize or develop abstract techniques using AI/ML--I think for most use cases we can use the source document as a direct reference for how the PDF document should be annotated. We should use as much information about the structured and machine readable source document as possible in order to reduce inexact and heuristic matches. Let's start with building the benchmarks and your textual analysis of the project. Don't do any major refactors yet, if we are able to successfully have benchmarks, those should feed into our work.

## Prompt 19

Excellent. Now, can you plan the fixes that you have enumerated above? I would like for you to provide detailed plans for the resolution of each rule violation and the reason for the failure. Please take as much time as necessary to do this and document your plan for my review. Don't begin your work until I have had a chance to review the plan.

## Prompt 20

Great, I left Feedback in two places. Please review, answer my questions, and allow me to verify your responses before proceeding.

## Prompt 21

Let's update the plan and proceed with the work!

## Prompt 22

Excellent! Do you have a plan for the external corpus findings? If not, let's start there. Then, let's make this our standard benchmark. Select a few representative theory assignments or exams as well. Then let's make that external benchmark our iteration loop. Also, let's expand our external benchmark. Can you collect more documents from a variety of EDU sites? I would like to ensure that we cover various branches of computer science as well. let's make sure to include some systems research and homeworks, machine learning/ai, graphics and vr, data mining, theory, discrete math, etc. Try to add more beamer examples as well -- many faculty use beamer slides for CS work. You can use github as well to look for course websites and materials.

## Prompt 23

Yes let's do it! (re: planning and implementing link annotation fix)

## Prompt 24

Let's run --fix-encoding by default then, since that fixes most violations. Are there downsides to this?

## Prompt 25

I'd like to now consolidate our benchmarking and demos to be based around the external benchmarks. Let's also update the Makefile and the UI. Let's also look at how we can make the UI informative about the changes that were made. Please audit the scripts for proper collection of changes into reports to be displayed by the terminal and IO. Let's add verapdf validation as a step to validate the before/after output in the web UI. We don't need this for CLI since the user can run this manually. But adding a script that runs verapdf before, our tool, then after would be a userful contribution or enhancement to the app.

## Prompt 26

For our service version, will we have races on file-based manipulations, or are you properly using isolated temporary directories? Do we have any server state that would be raced over for concurrent requests? Let's also take some screenshots of the web UI and the before/after validation in order to update the readme. Or at least some sample CLI output that includes the verapdf results. Finally, let's take a pass over the project and look for opportunities to reevaluate our abstractions for their appropriateness as the code has evolved, and look for opportunities for simplification. If there are none, that's okay. Give me a plan before any major refactors.

## Prompt 27

Perfect. Let's do your minor simplifications. Let's move the bencharks out of benchmarks/external and just into benchmarks/ -- eliminating the concept of an external benchmark and just having one collection of benchmarks. Demos should just be runs on the benchmarks. Make sense? Finally, update the prompts.md file with our prompts from this session.

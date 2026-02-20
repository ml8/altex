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

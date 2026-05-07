## What the student knows

* Dockerfile: FROM, WORKDIR, COPY, RUN, CMD
* Multi-stage: AS builder, COPY --from=builder, alpine images
* Networking: docker network create, --network, DNS by container name
* Compose: services, build: ., image:, ports, env_file, auto-networking
* CI pattern: fail-fast, no dev deps in prod image, cache layering
* Registry: docker tag, push, pull — full address format is `registry/username/name:version`
* Docker Hub implies registry, requires username prefix
* Local registry: `localhost:5000/name:tag`, no username needed
* Private registry: full prefix before username
* Tag is a pointer (symlink-like), push sends the layers to the registry in the prefix
* Running directly from full tag works without retagging
* GitHub Actions workflow structure: `name`, `on`, `jobs`, `runs-on`, `steps`, `uses`, `run`
* `actions/checkout@v4` is needed before build steps so the repository contents are available
* Basic GitHub Actions trigger syntax for pushes to `main`
* Docker build syntax in CI: `docker build -t myapp:latest .`
* Docker login to Hub with secrets: `${{ secrets.DOCKERHUB_USERNAME }}` and `${{ secrets.DOCKERHUB_TOKEN }}`
* Docker push must match the built tag exactly
* Combining shell commands in one `run: |` block keeps temporary variables like `SHORT_SHA` available for build/push
* Building and pushing a Docker image in one GitHub Actions step using a short commit SHA tag
* Step order in CI: checkout, login, build, push
* CI variables set in one step do not persist to later steps unless explicitly exported
* Docker build caching in GitHub Actions using `docker/setup-buildx-action@v3`
* `docker/build-push-action@v5` can build and push while reusing cache
* `cache-from` reads previously stored layers to speed up the current build
* `cache-to` stores newly built layers for future reuse
* Remote registry cache can be configured with `type=registry,ref=...`
* Build cache references should use the full image path, e.g. `mika/myapp:buildcache`
* Using `push: true` with build-push-action is the standard CI/CD pattern for publishing images
* Build cache can be shared across CI runs to make later builds much faster after a cold first build
* Multi-tag pushes in GitHub Actions: tagging one build with more than one tag, such as `latest` and a short SHA, before pushing
* Publishing multiple image tags from the same build so one image can be referenced by both a moving tag and an immutable tag

## Patterns to reinforce (common mistakes)

* COPY before RUN (forgot dependencies before install)
* Image names: postgres:15 not postgresql-15
* CMD: double quotes ["python", "app.py"] not single quotes
* pip install -r (not -f, don't forget "install")
* package-lock.json not package-lock-json, npm run build not npm build
* `docker tag` takes two args: source and destination
* Push destination must match the tag exactly — can't push an untagged name
* Full registry path needed as source in `docker tag` when retagging a pulled image
* YAML structure (on vs jobs, uses, missing runs-on)
* Misusing Docker (docker run for tests, bad build/tag syntax)
* Tag confusion (@ vs :)
* Cache flag syntax
* Remember to include `actions/checkout@v4` before Docker builds in GitHub Actions
* Build and push tags must match exactly, including registry/username and tag value
* GitHub Actions expressions like `${{ github.sha::7 }}` are not valid; use shell tools to shorten SHA
* Step-local shell variables do not carry into later steps
* `docker login` should be placed before push, and usually before the build/push block for clarity
* `docker login` command syntax in workflow steps should not include stray punctuation
* For registry-backed caching, use the full repository path in `cache-from` / `cache-to`, not a bare image name
* `cache-from` and `cache-to` need to point at the same cache reference for the cache to be reused effectively
* Initial cache-enabled builds may still be slow because the cache starts cold
* When doing multi-tag pushes, it is easy to tag only one name and forget to push the second tag
* When publishing both `latest` and a SHA tag, both tags must be applied to the same built image

## Side quests: Dynamic topics

Completed:

1. Python single-stage (3 attempts)
2. PHP two-stage (Apache + Composer)
3. TypeScript two-stage (Node builder + Alpine)
6. Custom Postgres + pgvector (manual + compose)
7. GitHub Actions CI for Docker build/push
8. Advanced Docker caching in CI

Available:

4. Java Spring Boot (Maven + JRE)
5. Go single-binary
9. Multiple tags per build
10. Push to private registry

## Progress - Current state

* Next time, continue Module 6 with multi-tag pushes in GitHub Actions, making sure one build publishes both `latest` and a short-SHA tag.
* If staying on side quests, pick Java Spring Boot, Go single-binary, or move into the remaining registry-focused side quest about pushing to a private registry.
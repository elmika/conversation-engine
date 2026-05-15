## What the student knows

* Dockerfile instructions: `FROM`, `WORKDIR`, `COPY`, `RUN`, `CMD`
* Multi-stage builds with `AS builder`, `COPY --from=builder`, and slim final images like `alpine`
* Docker networking: `docker network create`, `--network`, and container-name DNS resolution
* Docker Compose basics: `services`, `build: .`, `image:`, `ports`, `env_file`, and auto-networking
* CI pattern: fail fast, avoid dev dependencies in production images, and use cache layering
* Registry workflow: `docker tag`, `docker push`, `docker pull`, and the full image address format `registry/username/name:version`
* Docker Hub behaves as a registry and requires a username prefix in image tags
* Local registry images use `localhost:5000/name:tag` with no username prefix
* Private registry login targets use the host only, like `registry.example.com`
* Image tags still use the full repository path when pushing to a private registry
* `docker tag` source can be a pulled image with a full registry path
* Tag is a pointer/symlink-like reference, and pushing sends the layers for that tag’s repository path
* You can run directly from a full tag without retagging first
* `docker run` syntax is `docker run [OPTIONS] IMAGE [COMMAND] [ARG...]`
* `docker run -p 8080:80 --rm -d nginx:alpine` maps ports, detaches, and auto-removes the container
* `docker run --rm -it ubuntu /bin/bash` starts an interactive Ubuntu shell and removes the container on exit
* `-i` keeps STDIN open and `-t` allocates a pseudo-TTY; together `-it` makes an interactive terminal session
* `TTY` in Docker context means a terminal-like session
* `-d` runs a container in detached/background mode
* `--rm` automatically removes a container after it stops
* `--restart=always` restarts a container automatically when it exits, as long as it was not manually stopped
* `docker run -d --restart=always -p 8080:8080 alpine:latest sh -c "busybox httpd -f -p 8080"` starts a minimal Alpine HTTP server in detached mode
* Alpine can run a simple HTTP server via BusyBox `httpd`
* `docker ps` lists running containers
* `docker logs <container-name-or-id>` shows a container’s output
* GitHub Actions workflow structure: `name`, `on`, `jobs`, `runs-on`, `steps`, `uses`, `run`
* Top-level GitHub Actions structure includes `name`, `on`, and `jobs`
* `jobs` contains job IDs like `build`, each with `runs-on` and `steps`
* `steps` entries must use either `- uses:` or `- run:`
* `actions/checkout@v4` is needed before Docker build steps so the repo contents are available
* Basic GitHub Actions push trigger syntax for `main`
* Docker build syntax in CI: `docker build -t myapp:latest .`
* Docker login to Docker Hub with secrets: `${{ secrets.DOCKERHUB_USERNAME }}` and `${{ secrets.DOCKERHUB_TOKEN }}`
* `docker/login-action` uses the registry host only, not the full image path
* Docker push must match the built tag exactly
* Step order in CI: checkout, login, build, push
* Combining shell commands in one `run: |` block keeps temporary variables like `SHORT_SHA` available for build/push
* Step-local shell variables do not persist to later steps unless exported
* Short SHA can be written to `$GITHUB_OUTPUT` and reused later as `${{ steps.short.outputs.short }}`
* GitHub Actions expressions like `${{ github.sha::7 }}` are not valid for shortening SHA values
* Building and pushing an image in one GitHub Actions step using a short commit SHA tag
* Multi-tag pushes in GitHub Actions: tagging one build with both `latest` and a short SHA before pushing
* Publishing multiple image tags from the same build so one image can be referenced by both a moving tag and an immutable tag
* `docker/setup-buildx-action@v3` prepares a buildx builder; it does not build the image by itself
* `docker/build-push-action@v5` can build and push while reusing cache
* Default Docker build context in `build-push-action` is the repository root (`.`)
* `docker/build-push-action` usually should include `context: .` explicitly for clarity
* `push: true` with build-push-action is the standard CI/CD pattern for publishing images
* `cache-from` reads previously stored layers to speed up the current build
* `cache-to` stores newly built layers for future reuse
* Remote registry cache can be configured with `type=registry,ref=...`
* Build cache references should use the full image path, e.g. `mika/myapp:buildcache`
* For registry-backed caching, `cache-from` / `cache-to` should use the full repository path, not a bare image name
* `cache-from` and `cache-to` need to point at the same cache reference for the cache to be reused effectively
* Build cache can be shared across CI runs to make later builds much faster after a cold first build
* On a first cache-enabled run, the cache is still cold and the build may be slower
* Private registry workflows: login target is the host only, while image tags and cache refs use the full repository path
* Production workflow patterns: `.dockerignore`, secrets, graceful shutdown, restart policies, logging, resource limits

## Patterns to reinforce (common mistakes)

* COPY before RUN when dependencies need to be installed first
* Image names: `postgres:15` not `postgresql-15`
* CMD should use JSON array syntax with double quotes, e.g. `["python", "app.py"]`
* `pip install -r` includes `install` and uses `-r` correctly
* File naming: `package-lock.json` not `package-lock-json`
* npm scripts: `npm run build`, not `npm build`
* `docker tag` takes two args: source and destination
* Push destination must match the tag exactly — cannot push an untagged name
* When retagging a pulled image, use the full registry path as the source
* YAML structure mistakes: `on` vs `jobs`, missing `runs-on`, or incorrect `uses` placement
* Misusing Docker for tasks like testing instead of building the image or running the container appropriately
* Tag confusion between `@` and `:`
* Cache flag syntax errors
* Remember to include `actions/checkout@v4` before Docker builds in GitHub Actions
* Build and push tags must match exactly, including registry/username and tag value
* `docker login` should be placed before push, and usually before the build/push block for clarity
* `docker/login-action` takes the registry host only, not the full image path
* `docker/build-push-action` should usually specify `context: .` explicitly
* When doing multi-tag pushes, it is easy to tag only one name and forget to push the second tag
* When publishing both `latest` and a SHA tag, both tags must be applied to the same built image
* `docker/login-action` takes the registry host only, not the full image path
* `docker/build-push-action` should usually specify `context: .` explicitly
* `docker logs` is plural, not `docker log`
* `-p` is a Docker CLI option and must go before the image name, not inside the container command
* The container command string needs correct quoting when using `sh -c`
* `--restart=always` still requires a long-running process; a container that exits immediately will just restart repeatedly

## Side quests: Dynamic topics

Completed:

1. Python single-stage (3 attempts)
2. PHP two-stage (Apache + Composer)
3. TypeScript two-stage (Node builder + Alpine)
6. Custom Postgres + pgvector (manual + compose)
7. GitHub Actions CI for Docker build/push
8. Advanced Docker caching in CI
9. Multiple tags per build
10. Deploy with Docker: restart policies, logs, and simple HTTP servers

Available:

4. Java Spring Boot (Maven + JRE)
5. Go single-binary
10. Push to private registry

## Progress - Current state

* Next time, continue with remaining registry-focused work: pushing to a private registry and verifying the first push/pull with a build cache.
* If staying on side quests, pick Java Spring Boot or Go single-binary.
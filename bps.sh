#!/bin/bash
set -e  # Exit on any error

# Configuration
GITHUB_USER="stephenclau"
DOCKERHUB_USER="slautomaton"
IMAGE_NAME="factorio-isr"
VERSION="${1:-latest}"  # Use first argument or default to 'latest'

# Read tokens from files (secure approach)
GITHUB_TOKEN=$(cat ~/.secrets/GITHUB_TOKEN.txt)
DOCKERHUB_TOKEN=$(cat ~/.secrets/DOCKER_TOKEN.txt)

echo "Building image version: $VERSION"
docker build -t ghcr.io/$GITHUB_USER/$IMAGE_NAME:$VERSION \
             -t $DOCKERHUB_USER/$IMAGE_NAME:$VERSION \
             .

echo "Logging in to GHCR..."
echo "$GITHUB_TOKEN" | docker login ghcr.io -u $GITHUB_USER --password-stdin

echo "Logging in to Docker Hub..."
echo "$DOCKERHUB_TOKEN" | docker login -u $DOCKERHUB_USER --password-stdin

echo "Pushing to GHCR..."
docker push ghcr.io/$GITHUB_USER/$IMAGE_NAME:$VERSION

echo "Pushing to Docker Hub..."
docker push $DOCKERHUB_USER/$IMAGE_NAME:$VERSION

echo "✓ Successfully pushed $IMAGE_NAME:$VERSION to both registries"

#!/bin/bash
set -e  # Exit on any error

# Configuration
read -p "Enter GitHub username: " GITHUB_USER
read -p "Enter Docker Hub username: " DOCKERHUB_USER
read -p "Enter desired image name: " IMAGE_NAME
read -p "Enter image version (default: latest): " VERSION=${VERSION:-latest}

# Read tokens from files (secure approach)
GHCR_TOKEN=$(cat ~/.secrets/GHCR_TOKEN.txt)
DOCKERHUB_TOKEN=$(cat ~/.secrets/DOCKER_TOKEN.txt)

echo "Building image version: $VERSION"
docker build -t ghcr.io/$GITHUB_USER/$IMAGE_NAME:$VERSION \
             -t $DOCKERHUB_USER/$IMAGE_NAME:$VERSION \
             .

echo "Logging in to GHCR..."
echo "$GHCR_TOKEN" | docker login ghcr.io -u $GITHUB_USER --password-stdin

echo "Logging in to Docker Hub..."
echo "$DOCKERHUB_TOKEN" | docker login -u $DOCKERHUB_USER --password-stdin

echo "Pushing to GHCR..."
docker push ghcr.io/$GITHUB_USER/$IMAGE_NAME:$VERSION

echo "Pushing to Docker Hub..."
docker push $DOCKERHUB_USER/$IMAGE_NAME:$VERSION

echo "✓ Successfully pushed $IMAGE_NAME:$VERSION to both registries"

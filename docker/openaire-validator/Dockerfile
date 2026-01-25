# Multi-stage Dockerfile to build OpenAIRE CRIS Validator and provide a runnable image
ARG REPO_URL="https://github.com/EuroCRIS/openaire-cris-validator.git"
ARG REPO_REF="main"

FROM maven:3.9.5-eclipse-temurin-17 AS builder
ARG REPO_URL
ARG REPO_REF
WORKDIR /build
# Install tools and try to download a prebuilt JAR from GitHub releases.
# If no release asset is found, fall back to cloning and building from source.
RUN apt-get update && apt-get install -y git curl ca-certificates && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
		# 1) Try Maven Central: read metadata to get latest version and fetch jar-with-dependencies
		MAVEN_BASE="https://repo1.maven.org/maven2/org/eurocris/openaire-cris-validator"; \
		METADATA=$(curl -fsS "$MAVEN_BASE/maven-metadata.xml" || true); \
		VERSION=""; \
		if [ -n "$METADATA" ]; then \
			VERSION=$(echo "$METADATA" | sed -n 's:.*<latest>\(.*\)</latest>.*:\1:p' || true); \
			if [ -z "$VERSION" ]; then \
				VERSION=$(echo "$METADATA" | sed -n 's:.*<release>\(.*\)</release>.*:\1:p' || true); \
			fi; \
			if [ -z "$VERSION" ]; then \
				VERSION=$(echo "$METADATA" | tr "\n" " " | sed -n 's:.*<version>\([^<]*\)</version>.*:\1:p' || true); \
			fi; \
		fi; \
		FOUND=0; \
		if [ -n "$VERSION" ]; then \
			for SUF in "-jar-with-dependencies.jar" ".jar"; do \
				URL="$MAVEN_BASE/$VERSION/openaire-cris-validator-$VERSION$SUF"; \
				echo "Trying $URL"; \
				if curl -fL -o /build/openaire.jar "$URL"; then FOUND=1; break; fi; \
			done; \
		fi; \
		# 2) If not found on Maven Central, try GitHub releases API for any jar asset
		if [ "$FOUND" -eq 0 ]; then \
			ASSET_URL=$(curl -fsS https://api.github.com/repos/EuroCRIS/openaire-cris-validator/releases/latest | sed -n 's/.*"browser_download_url": "\(.*jar.*\)".*/\1/p' | head -n1 || true); \
			if [ -n "$ASSET_URL" ]; then \
				echo "Downloading release asset from GitHub: $ASSET_URL"; \
				curl -L -o /build/openaire.jar "$ASSET_URL" && FOUND=1 || true; \
			fi; \
		fi; \
		# 3) Fall back to building from source inside the image (slow). This path is a fallback only.
		if [ "$FOUND" -eq 0 ]; then \
			echo "No prebuilt artifact found; building from source."; \
			git clone --depth 1 --branch main https://github.com/EuroCRIS/openaire-cris-validator.git repo; \
			# fetch guidelines as an archive to avoid potential git auth issues in some build envs
			mkdir -p /build/guidelines-cris-managers; \
			# try cloning guidelines repo directly into expected location
			git clone --depth 1 --branch develop https://github.com/openaire/guidelines-cris-managers.git /build/guidelines-cris-managers || true; \
			if [ ! -d /build/guidelines-cris-managers/schemas ]; then git clone --depth 1 --branch main https://github.com/openaire/guidelines-cris-managers.git /build/guidelines-cris-managers || true; fi; \
			cd repo; \
			# Patch pom.xml so the xml-maven-plugin uses a file: URI for the external catalog
			sed -i "s|<catalog>\${guidelines.project.dir}/schemas/catalog.xml</catalog>|<catalog>file:\${guidelines.project.dir}/schemas/catalog.xml</catalog>|g" pom.xml || true; \
			# Run Maven and explicitly set guidelines.project.dir to absolute path
			mvn -DskipTests -Dguidelines.project.dir=/build/guidelines-cris-managers package -P '!uberjar' || mvn -DskipTests -Dguidelines.project.dir=/build/guidelines-cris-managers package; \
			JAR=$(ls target/*jar-with-dependencies*.jar target/*-jar.jar 2>/dev/null | head -n1 || true); \
			if [ -z "$JAR" ]; then echo "Build succeeded but no jar found"; exit 1; fi; \
			cp "$JAR" /build/openaire.jar; \
		fi

FROM eclipse-temurin:17-jre AS runtime
WORKDIR /opt/openaire
COPY --from=builder /build/repo/target/openaire-cris-validator-*jar-with-dependencies.jar /opt/openaire/openaire.jar
COPY validate.sh /usr/local/bin/validate.sh
RUN chmod +x /usr/local/bin/validate.sh && mkdir -p /opt/openaire/logs
VOLUME ["/opt/openaire/logs"]
ENV ENDPOINT=""
ENV LOOP_INTERVAL="0"
ENTRYPOINT ["/usr/local/bin/validate.sh"]

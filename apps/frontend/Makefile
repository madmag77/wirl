.PHONY: install install-dev lint format run build preview test clean

# Configuration
HOST?=0.0.0.0
PORT?=3000

# Node.js and npm commands
NPM := npm

install:
	$(NPM) install

install-dev: install
	@echo "Frontend dev dependencies installed with npm install"

lint:
	$(NPM) run lint

format:
	@echo "Frontend formatting not configured yet - consider adding prettier"

run:
	$(NPM) run dev -- --host $(HOST) --port $(PORT)

build:
	$(NPM) run build

preview:
	$(NPM) run preview

test:
	$(NPM) run test

clean:
	rm -rf node_modules dist
	$(NPM) cache clean --force

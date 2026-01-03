# Makefile for xaffinity MCP plugin
#
# This builds the Claude Code plugin by creating a ZIP archive
# of the MCP server files for distribution.

PLUGIN_DIR := .claude-plugin
ZIP_FILE := $(PLUGIN_DIR)/xaffinity-mcp-plugin.zip
VERSION_FILE := VERSION

# MCP server files to include in ZIP
MCP_FILES := \
	xaffinity-mcp.sh \
	xaffinity-mcp-env.sh \
	VERSION \
	FRAMEWORK_VERSION \
	COMPATIBILITY

# MCP server directories to include in ZIP
MCP_DIRS := \
	completions \
	lib \
	prompts \
	providers \
	resources \
	scripts \
	server.d \
	tools

.PHONY: plugin clean verify test-plugin help

# Default target: build the plugin ZIP
plugin: clean
	@echo "Building plugin ZIP..."
	@rm -f "$(ZIP_FILE)"
	@zip -q "$(ZIP_FILE)" $(MCP_FILES)
	@for dir in $(MCP_DIRS); do \
		if [ -d "$$dir" ]; then \
			zip -qr "$(ZIP_FILE)" "$$dir"; \
		fi; \
	done
	@# Copy VERSION to plugin dir for version comparison at runtime
	@cp "$(VERSION_FILE)" "$(PLUGIN_DIR)/VERSION"
	@echo "Plugin built: $(ZIP_FILE)"
	@echo "Version: $$(cat $(VERSION_FILE))"
	@echo "Size: $$(du -h "$(ZIP_FILE)" | cut -f1)"

# Verify the ZIP contents
# Expected ZIP structure (flat, no subdirectory wrapper):
#   xaffinity-mcp.sh
#   xaffinity-mcp-env.sh
#   VERSION
#   FRAMEWORK_VERSION
#   COMPATIBILITY
#   tools/
#   prompts/
#   ...
verify:
	@echo "Verifying plugin ZIP..."
	@test -f "$(ZIP_FILE)" || (echo "Error: ZIP not found" && exit 1)
	@test -f "$(PLUGIN_DIR)/VERSION" || (echo "Error: VERSION not found" && exit 1)
	@echo "Bundle version: $$(cat $(PLUGIN_DIR)/VERSION)"
	@unzip -l "$(ZIP_FILE)" | head -20
	@echo "..."
	@echo "Total files: $$(unzip -l "$(ZIP_FILE)" | tail -1)"

# Test the plugin extraction and MCP server
test-plugin: plugin
	@echo "Testing plugin extraction..."
	@cd $(PLUGIN_DIR) && rm -rf .mcp-extracted
	@cd $(PLUGIN_DIR) && ./xaffinity-mcp.sh --help >/dev/null 2>&1 || true
	@test -x $(PLUGIN_DIR)/.mcp-extracted/xaffinity-mcp.sh || \
		(echo "FAIL: Extraction did not create executable" && exit 1)
	@test -f $(PLUGIN_DIR)/.mcp-extracted/VERSION || \
		(echo "FAIL: VERSION not extracted" && exit 1)
	@echo "PASS: Plugin extraction test"

# Clean build artifacts
clean:
	@echo "Cleaning..."
	@rm -f "$(ZIP_FILE)"
	@rm -f "$(PLUGIN_DIR)/VERSION"
	@rm -rf "$(PLUGIN_DIR)/.mcp-extracted"

help:
	@echo "Available targets:"
	@echo "  plugin      - Build the plugin ZIP archive"
	@echo "  verify      - Verify ZIP contents"
	@echo "  test-plugin - Build and test extraction"
	@echo "  clean       - Remove build artifacts"
	@echo "  help        - Show this help message"

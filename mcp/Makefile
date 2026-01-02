# Makefile for xaffinity MCP plugin
#
# This builds the Claude Code plugin by copying MCP server files
# into .claude-plugin/ where they can be installed from the marketplace.

PLUGIN_DIR := .claude-plugin

# MCP server files to copy
MCP_FILES := \
	xaffinity-mcp.sh \
	xaffinity-mcp-env.sh \
	VERSION \
	.mcp-bash-version

# MCP server directories to copy
MCP_DIRS := \
	completions \
	lib \
	prompts \
	providers \
	resources \
	scripts \
	server.d \
	tools

.PHONY: plugin clean help

# Default target
plugin: clean
	@echo "Building plugin..."
	@for file in $(MCP_FILES); do \
		if [ -f "$$file" ]; then \
			cp "$$file" "$(PLUGIN_DIR)/" && echo "  Copied $$file"; \
		fi; \
	done
	@for dir in $(MCP_DIRS); do \
		if [ -d "$$dir" ]; then \
			cp -r "$$dir" "$(PLUGIN_DIR)/" && echo "  Copied $$dir/"; \
		fi; \
	done
	@echo "Plugin built successfully in $(PLUGIN_DIR)/"

clean:
	@echo "Cleaning plugin directory..."
	@for file in $(MCP_FILES); do \
		rm -f "$(PLUGIN_DIR)/$$file"; \
	done
	@for dir in $(MCP_DIRS); do \
		rm -rf "$(PLUGIN_DIR)/$$dir"; \
	done
	@echo "Clean complete"

help:
	@echo "Available targets:"
	@echo "  plugin  - Build the plugin (copies MCP files to .claude-plugin/)"
	@echo "  clean   - Remove copied MCP files from .claude-plugin/"
	@echo "  help    - Show this help message"

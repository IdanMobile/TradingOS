# Brain, hands, and skill security

## Brain and hands separation

Keep the supervisor Brain separate from execution Hands.

### Brain responsibilities

- research and source evaluation;
- strategy and architecture reasoning;
- system supervision;
- risk and security review;
- experiment design;
- roadmap and decision records.

### Hands responsibilities

- market-data connectors;
- backtest engines;
- paper/testnet adapters;
- broker/exchange order adapters;
- wallet or blockchain integrations;
- monitoring and notification systems.

The Brain may inspect or recommend changes to Hands. It must not silently acquire their credentials or execution authority.

## Third-party skill review

Treat every external skill, plugin, script, MCP server, and marketplace package as executable supply-chain material, not passive documentation.

Before use:

- inspect all instructions and scripts;
- identify network, shell, filesystem, wallet, and credential access;
- verify source and maintainer;
- pin or record the version and commit;
- remove unrelated instructions and hidden prompts;
- test in an isolated environment;
- use read-only or testnet permissions first;
- record what was accepted and rejected.

Do not install a skill solely because it has downloads, stars, a marketplace listing, or a confident description.

## Permission boundaries

The supervisor skill is instruction-only initially. It must not:

- request private keys or withdrawal permissions;
- sign blockchain transactions;
- place, cancel, or modify live orders;
- change risk limits without an approved decision;
- install dependencies or remote skills silently;
- upload project data or secrets to external services;
- write to production systems.

If external research tools are available, use them for public information only and preserve source provenance.

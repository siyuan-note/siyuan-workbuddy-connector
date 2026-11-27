# Changelog

All notable changes to the SiYuan WorkBuddy connector are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.5] - 2026-11-27

### Changed

- Renamed the connector to **思源笔记 / SiYuan** (previously 思源笔记官方连接器 / SiYuan
  Official Connector) after the platform resolved the name conflict with the earlier occupant.

## [1.0.4] - 2026-11-25

### Fixed

- Removed `minWorkbuddyVersion` so the connector is not filtered out of the mobile App
  connector market. The mobile App uses an independent version line (2.9.1), so the previous
  `4.23.0` floor hid the connector on phones even though the desktop client (5.11.3) showed it.

## [1.0.3] - 2026-11-21

### Fixed

- Connection failure across all machines: the default `SIYUAN_HOST` value was `127.0.0.1:6806`,
  and the client-side hostname check rejects any value containing a colon, throwing
  `Invalid hostname variable SIYUAN_HOST`. The MCP server was therefore never registered and
  every request failed with `MCP server "connector:siyuan" is not registered`.
  The port now has its own field, `SIYUAN_PORT` (default `6806`).

### Changed

- `SIYUAN_HOST` is explicitly documented as "host only, no scheme, no port, no path", and
  `SIYUAN_PORT` as "digits only", with a public HTTPS example (`443`).

## [1.0.2] - 2026-11-21

### Added

- `SCHEMA` field, so a single connector covers both a local kernel over `http` and a public
  deployment behind a TLS reverse proxy over `https`.
- Bilingual labels and field descriptions in the connection form.

### Fixed

- Field descriptions now spell out what must not be included (scheme, port, path, whitespace),
  which was the source of most setup mistakes.

## [1.0.0] - 2026-11-21

### Added

- First version: MCP Streamable HTTP transport against SiYuan's built-in `/mcp` endpoint,
  API token authentication, and the `skills/siyuan` usage guide.

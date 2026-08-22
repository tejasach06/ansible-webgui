# Frontend

The Ansible WebGUI frontend is a TypeScript-based single-page application built with React, Tailwind CSS, and Vite.

## Stack

- **Framework**: React 18.3.1
- **Router**: react-router-dom 7.18.2
- **Data Fetching**: @tanstack/react-query 5.66.0
- **Build Tool**: Vite 8.2.1
- **Language**: TypeScript 5.7.3
- **Styling**: Tailwind CSS 3.4.17
- **Editor**: Monaco 0.52.2
- **Terminal**: @xterm/xterm 5.5.0

## Layout

- `src/api/`: API modules, where each module corresponds to a backend router of the same name.
- `src/components/`: Reusable UI components.
- `src/lib/`: Library utilities, including `api.ts` which provides the core `apiFetch<T>()` function used by all API modules.
- `src/pages/`: Page-level components, such as `ApprovalReviewPage`, `JobDetailPage`, `ProjectsPage`, `ProjectWorkspacePage`, and `PipelineRunPage`.

## Commands

- `npm run dev`: Start the Vite development server.
- `npm run typecheck`: Run TypeScript type checking.
- `npm run build`: Compile TypeScript and build the project.
- `npm run preview`: Preview the production build.

## Containerized Deployment

In the containerized setup, the frontend is built and served by Nginx. The production build process is handled by the `Containerfile.web` and the Nginx configuration is defined in `nginx.conf`.

## Cross-links

- [Repository README](../README.md)
- [Architecture Guide](../docs/architecture.md)
- [Contributing Guide](../CONTRIBUTING.md)

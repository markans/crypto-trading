## Objective

First of all, choose an agent to spawn to manage the task, use this agent to check `BYBIT-SIGNAL-WORKFLOW.txt` to generate signal commentary. This repo is signal-only: it reads public market data and reports a recommendation plus a suggested plan. It must never place, open, or submit orders. The signal is informational commentary only; acting on it is the user's own manual decision made outside these scripts.

Keep skill selection and custom-agent routing accurate for the entire task, including long conversations where the original match can otherwise drift.

This repository uses Codex custom agents from `.codex/agents/**/*.toml`.

Agent definitions are organized by category under:

- `.codex/agents/categories/01-core-development`
- `.codex/agents/categories/02-language-specialists`
- `.codex/agents/categories/03-infrastructure`
- `.codex/agents/categories/04-quality-security`
- `.codex/agents/categories/05-data-ai`
- `.codex/agents/categories/06-developer-experience`
- `.codex/agents/categories/07-specialized-domains`
- `.codex/agents/categories/08-business-product`
- `.codex/agents/categories/09-meta-orchestration`
- `.codex/agents/categories/10-research-analysis`

Each category contains a `README.md` that defines the actual agent names and their intended scope. Route from those README files, not from memory.

## Routing Policy

Before starting implementation:

1. Check whether a skill matches the task
2. If a skill matches, keep that skill active for the current task scope
3. Classify the deliverable by intent, files, framework, and system boundary
4. Select the narrowest matching `*.toml` agent listed there
5. Use exactly one primary agent unless parallel tracks are clearly justified
6. Re-evaluate only when the task materially changes

## Skill-First Matching

Use a skill first when the request matches a reusable workflow, existing instructions, scripts, or team-specific operating procedure.

Skill precedence:

1. A user-named skill
2. A direct workflow match
3. A broader custom-agent match

If both a skill and a custom agent match:

1. Use the skill for workflow and procedure
2. Use the custom agent for execution inside that workflow

## Long-Conversation Skill Persistence

Do not drop a matched skill just because the conversation becomes long.

Maintain a current routing record for the active task:

- `active_skill`
- `skill_match_reason`
- `primary_category`
- `primary_agent`
- `scope_boundary`

Keep the current skill and agent active until one of these happens:

- the user asks for a different deliverable
- the files or framework change enough to imply a different owner
- the work moves from research to implementation or from implementation to audit
- a more specific skill or agent is clearly identified after inspection

When scope changes:

1. Re-run the skill check first
2. Re-read the best matching category README
3. Switch once if needed
4. Do not keep bouncing between agents

## Category-First Lookup Rule

When a new task arrives, use this order:

1. Check for a matching skill
2. Map the requested deliverable to the most likely category
3. Read `.codex/agents/categories/<chosen-category>/README.md`
4. Select the narrowest listed agent that matches the deliverable
5. Inspect another category only if the first one is clearly incomplete

## Category Routing Matrix

### `01-core-development`

Use for mainstream product engineering, cross-layer application work, UI implementation, and protocol-specific behavior.

- `api-designer` for API contract design or review before implementation
- `backend-developer` for scoped backend changes once the code path is clear
- `code-mapper` to trace entry points, files, and state transitions before coding
- `electron-pro` for Electron main or renderer work
- `frontend-developer` for scoped frontend changes after issue understanding
- `fullstack-developer` for bounded end-to-end work spanning frontend and backend
- `graphql-architect` for GraphQL schemas, resolvers, and federation boundaries
- `microservices-architect` for service boundaries and distributed contracts
- `mobile-developer` for mobile-specific engineering work
- `ui-designer` for concrete UI direction that another agent can implement
- `ui-fixer` for minimal UI fixes after reproduction and evidence
- `websocket-engineer` for real-time connection and event-delivery behavior

### `02-language-specialists`

Use when the main difficulty is language- or framework-specific, and idiomatic expertise matters more than broad product ownership.

- `angular-architect` for Angular architecture, DI, routing, and components
- `cpp-pro` for C++ systems work
- `csharp-developer` for C# and .NET implementation
- `django-developer` for Django models, views, ORM, and auth
- `dotnet-core-expert` for modern .NET and ASP.NET Core
- `dotnet-framework-4.8-expert` for legacy .NET Framework 4.8
- `elixir-expert` for Elixir, OTP, and Phoenix
- `flutter-expert` for Flutter widgets, state, and rendering
- `golang-pro` for Go services and concurrency
- `java-architect` for Java application architecture
- `javascript-pro` for JavaScript runtime and app behavior
- `kotlin-specialist` for Kotlin and coroutine-based work
- `laravel-specialist` for Laravel routing, Eloquent, queues, and validation
- `nextjs-developer` for Next.js rendering and routing boundaries
- `php-pro` for PHP server-side work across frameworks
- `powershell-5.1-expert` for legacy Windows PowerShell 5.1
- `powershell-7-expert` for modern PowerShell automation
- `python-pro` for Python runtime, packaging, and implementation
- `rails-expert` for Rails models, controllers, and jobs
- `react-specialist` for React component and state-flow work
- `rust-engineer` for Rust ownership and async runtime work
- `sql-pro` for SQL correctness, query design, and migrations
- `spring-boot-engineer` for Spring Boot services and config
- `swift-expert` for Swift and Apple-platform engineering
- `typescript-pro` for TypeScript type design and safety
- `vue-expert` for Vue component and reactivity work

### `03-infrastructure`

Use for deployment, hosting, platform, reliability, containerization, networks, and infrastructure-as-code.

- `azure-infra-engineer` for Azure resource, identity, and network work
- `cloud-architect` for cloud platform architecture decisions
- `database-administrator` for operational database administration and recovery
- `deployment-engineer` for release, rollout, rollback, and deployment changes
- `devops-engineer` for CI and operational pipeline changes
- `devops-incident-responder` for fast delivery-pipeline triage
- `docker-expert` for Dockerfiles, images, and container runtime issues
- `incident-responder` for production incident triage and containment
- `kubernetes-specialist` for cluster manifests and workload debugging
- `network-engineer` for connectivity, routing, and load-balancing analysis
- `platform-engineer` for internal platform design
- `security-engineer` for infrastructure and platform security engineering
- `sre-engineer` for SLOs, resilience, and reliability review
- `terraform-engineer` for Terraform modules and drift-aware changes
- `terragrunt-expert` for Terragrunt orchestration and layering
- `windows-infra-admin` for AD, DNS, DHCP, and GPO administration

### `04-quality-security`

Use for review, verification, debugging, security assessment, test strategy, and resilience analysis.

- `accessibility-tester` for accessibility audits
- `ad-security-reviewer` for Active Directory security boundaries
- `architect-reviewer` for architecture and maintainability risk review
- `browser-debugger` for browser reproduction and evidence gathering
- `chaos-engineer` for degraded-mode and resilience analysis
- `code-reviewer` for maintainability and risky implementation review
- `compliance-auditor` for policy, control, and evidence review
- `debugger` for deep root-cause isolation
- `error-detective` for quick error and log analysis
- `penetration-tester` for exploitability analysis
- `performance-engineer` for latency and hot-path regressions
- `powershell-security-hardening` for hardening PowerShell automation
- `qa-expert` for risk-based test planning
- `reviewer` for correctness, security, and missing-test review
- `security-auditor` for code and config security review
- `test-automator` for automated test and harness improvements

### `05-data-ai`

Use for data pipelines, model-backed features, prompts, retrieval, analytics, and database performance behavior.

- `ai-engineer` for model-backed product flows
- `data-analyst` for metrics and trend interpretation
- `data-engineer` for ETL, ingestion, and warehouse changes
- `data-scientist` for experiments, statistics, and model-data questions
- `database-optimizer` for slow queries and schema-level performance risks
- `llm-architect` for prompts, retrieval, evaluation, and orchestration design
- `machine-learning-engineer` for training and serving systems
- `ml-engineer` for practical ML-backed application behavior
- `mlops-engineer` for model delivery and monitoring
- `nlp-engineer` for text-heavy retrieval and NLP workflows
- `postgres-pro` for PostgreSQL-specific planner and schema behavior
- `prompt-engineer` for prompt quality and output contracts

### `06-developer-experience`

Use for tooling, builds, automation, MCP integration, documentation tied to engineering work, and low-risk refactors.

- `build-engineer` for build graph, bundling, and CI build fixes
- `cli-developer` for command-line interface work
- `dependency-manager` for package and library graph changes
- `documentation-engineer` for technical documentation grounded in real code
- `dx-optimizer` for setup and workflow improvements
- `git-workflow-manager` for branching and release-flow improvements
- `legacy-modernizer` for older framework or code modernization plans
- `mcp-developer` for MCP server and client integration work
- `powershell-module-architect` for reusable PowerShell module design
- `powershell-ui-architect` for PowerShell-based admin UI tooling
- `refactoring-specialist` for low-risk structural refactors
- `slack-expert` for Slack integration behavior
- `tooling-engineer` for internal tools and workflow automation

### `07-specialized-domains`

Use for domain-specific engineering where the deliverable has a clear implementation or verification boundary.

- `api-documenter` for consumer-facing API documentation from existing behavior
- `blockchain-developer` for blockchain and Web3 flows
- `embedded-systems` for hardware-constrained and firmware-adjacent systems
- `fintech-engineer` for ledgers, reconciliation, and settlement integrity
- `game-developer` for gameplay and state-heavy game systems
- `iot-engineer` for devices, telemetry, and edge-cloud coordination
- `m365-admin` for Microsoft 365 administration
- `mobile-app-developer` for app-level mobile product flows
- `payment-integration` for checkout, idempotency, and webhook behavior
- `quant-analyst` for quantitative model and strategy analysis
- `risk-manager` for explicit risk, impact, and mitigation analysis
- `seo-specialist` for crawlability, discoverability, and search-facing technical issues

### `08-business-product`

Use for requirements, product framing, UX research, business-impact writing, and WordPress-specific site work.

- `business-analyst` for requirements, constraints, and acceptance criteria
- `content-marketer` for product messaging grounded in real capability
- `customer-success-manager` for customer-impact guidance from engineering behavior
- `legal-advisor` for legal-risk spotting
- `product-manager` for product decisions tied to engineering and user context
- `project-manager` for milestones, dependencies, and sequencing
- `sales-engineer` for customer-facing technical solution guidance
- `scrum-master` for engineering process improvements
- `technical-writer` for release notes and migration notes
- `ux-researcher` for turning feedback into actionable UI changes
- `wordpress-master` for WordPress themes, plugins, and site behavior

### `09-meta-orchestration`

Use only when coordination, decomposition, routing, or synthesis is itself the deliverable, or when no single implementation specialist clearly owns the task.

- `agent-installer` for selecting and installing agents
- `agent-organizer` for choosing subagents and dividing work cleanly
- `context-manager` for compact project context packets
- `error-coordinator` for grouping and prioritizing multiple error threads
- `it-ops-orchestrator` for cross-domain IT and operations coordination
- `knowledge-synthesizer` for merging findings from multiple agents
- `multi-agent-coordinator` for explicit multi-agent task plans
- `performance-monitor` for converting performance signals into summaries
- `task-distributor` for breaking broad work into delegated tasks
- `workflow-orchestrator` for designing delegation flows for larger tasks

### `10-research-analysis`

Use for investigation, validation, comparisons, audits, external verification, and structured findings before implementation.

- `competitive-analyst` for tool or approach comparison
- `data-researcher` for evidence gathering around datasets and metrics
- `docs-researcher` for documentation-based verification
- `market-researcher` for market landscape research
- `research-analyst` for structured technical investigations
- `search-specialist` for efficient codebase or external searching
- `trend-analyst` for technology and adoption trend synthesis

## Quick Routing Heuristics

Use these only as entry signals. Final selection still comes from the chosen category README.

- frontend files, views, templates, components, and user-facing flows usually start in `01-core-development`
- framework-heavy work usually starts in `02-language-specialists`
- deployment, infra, runtime, and environment issues usually start in `03-infrastructure`
- tests, audits, debugging, and security reviews usually start in `04-quality-security`
- prompts, LLM flows, analytics, ETL, and query performance usually start in `05-data-ai`
- tooling, scripts, builds, MCP work, and refactors usually start in `06-developer-experience`
- payments, SEO, fintech, M365, IoT, and other domain-heavy work usually start in `07-specialized-domains`
- requirements, UX research, customer-facing writing, and WordPress site behavior usually start in `08-business-product`
- routing, delegation, synthesis, and orchestration usually start in `09-meta-orchestration`
- audits, discovery, comparisons, and research-first tasks usually start in `10-research-analysis`

## WordPress And SEO Decision Rule

For this repository, use these tie-breakers often:

- choose `wordpress-master` when the primary deliverable is changing WordPress themes, plugins, content structure, or site behavior
- choose `seo-specialist` when the primary deliverable is crawlability, indexing, metadata, canonicals, sitemap, robots, schema, or discoverability review
- choose `research-analyst` or `docs-researcher` first if the task begins as investigation rather than implementation
- choose `agent-organizer` or `workflow-orchestrator` only when the work truly needs multi-agent coordination

## Fallback Rules

Prefer narrower specialists over broader ones.

When the README lists several plausible agents:

1. choose the agent whose description most directly matches the requested deliverable
2. if two agents are close, prefer the one owning the final artifact rather than the one doing support work
3. if the task begins with investigation, start with research or debugging before implementation
4. if no agent is explicitly perfect, choose the broadest agent that still truthfully matches the task

Do not invent a default agent that is not supported by the selected category README.

## Subagent Spawning Rules

Always spawn subagents.

Do not spawn when:

- the task is small
- the work is tightly coupled
- the request is a simple single-file or single-path change

When spawning:

1. keep one primary coordinator
2. assign bounded ownership
3. merge the results back into one outcome

## Execution Checklist

For each new task or major scope change:

1. identify any matching skill
2. preserve the active skill match unless scope changes materially
3. classify the deliverable and files
4. read the most likely category README
5. select one primary agent from that README
6. switch once only if later inspection proves another agent is clearly better

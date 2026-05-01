# Project: ONE-MP Agent (Python 3.11 + .NET 8/9, Microsoft Agent Framework)

> Cross-language repo. `classical_app/` + `shared/` (Python) and
> `agent_app/` + `shared/csharp/` (C# / .NET) live side by side, sharing
> the SQLite database and seed data. See
> `docs/agent-stack-decision-2026-04-29.md` for the pivot rationale.

## 🧱 Code Structure & Modularity

### Style & Formatting (automated)

#### Python (`classical_app/`, `shared/`, `eval/`, `tests/`)

**Python style is enforced by `ruff` — see `[tool.ruff]` in `pyproject.toml`
for the single source of truth** (line length, import order, blank lines,
quotes, etc.).

Before committing, always run:

```bash
ruff format . && ruff check --fix .
```

This is a shift-left gate. Code reviewers **must not re-litigate** anything
ruff owns (line length, blank lines, quote style, import order, trailing
commas, naming-case conventions, simple pyupgrade rewrites). If style drift
is detected, the reviewer's only acceptable response is "run ruff" — not an
enumerated list of violations.

Use PEP 484 type hints (`dict[str, int]`, not `typing.Dict[str, int]`).

#### C# / .NET (`agent_app/`, `shared/csharp/`)

**C# style is enforced by `dotnet format` against the repo `.editorconfig`
— single source of truth** (indentation, brace placement, using order,
naming conventions via `dotnet_naming_*`).

Before committing, always run:

```bash
dotnet format
```

Same shift-left rule as Python: reviewers must not re-litigate anything
`dotnet format` owns. The only acceptable response to style drift is
"run dotnet format".

Conventions:

- Target framework: .NET 8 (LTS) or .NET 9 — pinned in `*.csproj`
  `<TargetFramework>`.
- `<Nullable>enable</Nullable>` and `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`
  in every project. Nullable reference types are non-negotiable.
- File-scoped namespaces (`namespace Foo.Bar;`).
- `var` only when type is obvious from RHS; explicit type otherwise.
- `async` methods end in `Async`; pass `CancellationToken` through async
  call chains.

### File and Function Limits

- **Never create a file longer than 500 lines of code**. If approaching this
  limit, refactor by splitting into modules.
- **Functions should be under 50 lines** with a single, clear responsibility.
- **Classes should be under 100 lines** and represent a single concept or entity.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.

### Code Conventions

- Type hints on all public functions
- Docstrings on all public classes and non-trivial functions
- Use `loguru` for logging, not print statements
- No hardcoded paths — use Hydra config or pathlib relative to project root

## 🛠️ Development Setup

### Python

Use venv for dependencies.

- Virtual env: `source .venv/bin/activate` before any Python commands
- Dependencies: `pip install -e ".[dev]"` for dev install with extras

### C# / .NET

- SDK: install .NET 8 (LTS) or .NET 9 SDK (`dotnet --list-sdks` to check).
- Restore + build: `dotnet restore && dotnet build` from `agent_app/`.
- Run: `dotnet run --project agent_app/AgentApp.csproj` (project name TBD
  during scaffold).
- Tests: `dotnet test` (xUnit). Parity tests for `shared/csharp/` live
  alongside the C# port and mirror `tests/shared/test_business_rules.py`.

## 📋 Style & Conventions

### Docstring Standards

Use Google-style docstrings for all public functions, classes, and modules:

```python
def calculate_discount(
    price: Decimal,
    discount_percent: float,
    min_amount: Decimal = Decimal("0.01")
) -> Decimal:
    """
    Calculate the discounted price for a product.

    Args:
        price: Original price of the product
        discount_percent: Discount percentage (0-100)
        min_amount: Minimum allowed final price

    Returns:
        Final price after applying discount

    Raises:
        ValueError: If discount_percent is not between 0 and 100
        ValueError: If final price would be below min_amount

    Example:
        >>> calculate_discount(Decimal("100"), 20)
        Decimal('80.00')
    """
```

### Naming Intent

Case conventions (`snake_case`, `PascalCase`, `UPPER_SNAKE_CASE`) are enforced
by `ruff` (rule set `N`). What reviewers *should* evaluate is **naming intent**
— whether a name reflects domain meaning clearly. Cryptic abbreviations,
misleading names, or names that describe *how* rather than *what* are
semantic concerns and remain in-scope for human/LLM review.

## 🚨 Error Handling

### Exception Best Practices

```python
# Create custom exceptions for your domain
class PaymentError(Exception):
    """Base exception for payment-related errors."""
    pass

class InsufficientFundsError(PaymentError):
    """Raised when account has insufficient funds."""
    def __init__(self, required: Decimal, available: Decimal):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient funds: required {required}, available {available}"
        )

# Use specific exception handling
try:
    process_payment(amount)
except InsufficientFundsError as e:
    logger.warning(f"Payment failed: {e}")
    return PaymentResult(success=False, reason="insufficient_funds")
except PaymentError as e:
    logger.error(f"Payment error: {e}")
    return PaymentResult(success=False, reason="payment_error")

# Use context managers for resource management
from contextlib import contextmanager

@contextmanager
def database_transaction():
    """Provide a transactional scope for database operations."""
    conn = get_connection()
    transaction = conn.begin_transaction()
    try:
        yield conn
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        conn.close()
```

## 📝 Documentation Standards

### Code Documentation

- Every module should have a docstring explaining its purpose
- Public functions must have complete docstrings
- Complex logic should have inline comments with `# Reason:` prefix
- Keep README.md updated with setup instructions and examples
- Maintain CHANGELOG.md for version history

### API Documentation

```python
from fastapi import APIRouter, HTTPException, status
from typing import List

router = APIRouter(prefix="/products", tags=["products"])

@router.get(
    "/",
    response_model=List[Product],
    summary="List all products",
    description="Retrieve a paginated list of all active products"
)
async def list_products(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None
) -> List[Product]:
    """
    Retrieve products with optional filtering.

    - **skip**: Number of products to skip (for pagination)
    - **limit**: Maximum number of products to return
    - **category**: Filter by product category
    """
    # Implementation here
```

## 🛡️ Security Best Practices

### Security Guidelines

- Never commit secrets - use environment variables
- Validate all user input with Pydantic
- Use parameterized queries for database operations
- Implement rate limiting for APIs
- Keep dependencies updated with `uv`
- Use HTTPS for all external communications
- Implement proper authentication and authorization

### Example Security Implementation

```python
from passlib.context import CryptContext
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)
```

### Python Best Practices

- PEP 8: https://pep8.org/
- PEP 484 (Type Hints): https://www.python.org/dev/peps/pep-0484/
- The Hitchhiker's Guide to Python: https://docs.python-guide.org/

### C# / .NET Best Practices

- Framework design guidelines: https://learn.microsoft.com/dotnet/standard/design-guidelines/
- C# coding conventions: https://learn.microsoft.com/dotnet/csharp/fundamentals/coding-style/coding-conventions
- Nullable reference types: https://learn.microsoft.com/dotnet/csharp/nullable-references

## ⚠️ Important Notes

- **NEVER ASSUME OR GUESS** - When in doubt, ask for clarification
- **Always verify file paths and module names** before use
- **Keep CLAUDE.md updated** when adding new patterns or dependencies
- **Test your code** - No feature is complete without tests
- **Document your decisions** - Future developers (including yourself) will thank you

## 📂 Project Conventions

- **Implementation plans**: `plan/<feature-name>.md`
- **Git worktrees**: `.worktrees/` (project-local, gitignored)
- **Testing**: `pytest` for all tests, `unittest.mock` or `pytest-mock` for mocking

## 🚀 GitHub Flow Workflow Summary

main (protected) ←── PR ←── feature/your-feature
↓ ↑
deploy development

### Daily Workflow:

1. git checkout main && git pull origin main
2. git checkout -b feature/new-feature
3. Make changes + tests
4. git push origin feature/new-feature
5. Create PR → Review → Merge to main

---

## Code Exploration Policy
Always use jCodemunch-MCP tools — never fall back to Read, Grep, Glob, or Bash for code exploration.
- Before reading a file: use get_file_outline or get_file_content
- Before searching: use search_symbols or search_text
- Before exploring structure: use get_file_tree or get_repo_outline
- Call resolve_repo with the current directory first; if not indexed, call index_folder.

## Agent Framework & CopilotKit Policy

Before writing any code in `agent_app/` (C# / .NET) or `shared/csharp/`
that uses Microsoft Agent Framework or CopilotKit APIs, **query Context7
first** for the relevant topic. Never assume API signatures or
configuration from training data — these are preview / bleeding-edge
packages that change frequently.

| Library | Context7 ID |
|---|---|
| Microsoft Agent Framework | `/websites/learn_microsoft_en-us_agent-framework` |
| CopilotKit | `/copilotkit/copilotkit` |

**MS Learn zone pivots are mandatory.** Pages with `zone_pivot_groups:
programming-languages` default to C# in WebFetch / Context7 output but
contain *both* C# and Python versions interleaved. Always include
`?pivots=programming-language-csharp` in the URL when fetching C#
guidance for `agent_app/` — and `?pivots=programming-language-python`
when researching anything residual on the Python side. Cross-language
pattern leakage caused the multi-week derail that triggered the
2026-04-29 pivot.

Canonical C# entry points:

- AG-UI hosting: `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore`
  (`app.MapAGUI("/", agent)`).
- Agent runtime: `Microsoft.Agents.AI` (`AsAIAgent` extension on
  `Microsoft.Agents.AI.Foundry` `FoundryChatClient`).
- HITL: `ApprovalRequiredAIFunction` + `request_approval` synthetic
  client tool + bidirectional middleware (per
  `integrations/ag-ui/human-in-the-loop?pivots=programming-language-csharp`).
- Frontend: CopilotKit React via `HttpAgent` runtime registration (per
  CopilotKit MAF page).

Examples of when to query: `ApprovalRequiredAIFunction` constructor
options, `MapAGUI` route shape, `HttpAgent` registration / `threadId`
reset, streaming event types, middleware insertion order, `FoundryChatClient`
construction.

_This document is a living guide. Update it as the project evolves and new
patterns emerge._
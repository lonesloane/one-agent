# Refactor Candidates

After TDD cycle, look for:

- **Duplication** -> Extract function or class; name it after the concept it represents
- **Long functions** -> Break into private helpers (keep tests on the public interface)
- **Shallow modules** -> Combine pass-throughs or deepen the implementation
- **Feature envy** -> Move logic to where the data lives
- **Primitive obsession** -> Introduce a dataclass or value object (`@dataclass(frozen=True)`)
- **None returns** -> Use `Optional[T]` with explicit type hints to make absence explicit
- **None parameters** -> Introduce a factory method or a default/empty value object
- **Mutable DTOs** -> Replace with frozen dataclasses or Pydantic models; immutable by default
- **Complex conditionals** -> Use structural pattern matching (`match/case`) or polymorphism
- **Verbose collection pipelines** -> Rewrite with comprehensions or generator expressions
- **Existing code** the new code reveals as problematic (don't ignore it — refactor in a follow-up cycle)

**Never refactor while RED.** Get all tests GREEN first, then clean up.

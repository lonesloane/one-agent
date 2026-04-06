# Good and Bad Tests

## Good Tests

**Integration-style**: Test through real interfaces, not mocks of internal parts.

```python
# GOOD: Tests observable behavior
def test_user_can_checkout_with_valid_cart(checkout_service):
    cart = create_cart_with_product(some_product())

    result = checkout_service.checkout(cart, valid_payment_method())

    assert result.status == OrderStatus.CONFIRMED
```

Characteristics:

- Tests behavior callers care about
- Uses public API only — no access to private fields or internal state
- Survives internal refactors
- Describes WHAT, not HOW
- One logical assertion per test (or one concept per test class)

## Bad Tests

**Implementation-detail tests**: Coupled to internal structure.

```python
# BAD: Tests implementation — verifies HOW, not WHAT
def test_checkout_calls_payment_service_process(
    checkout_service, mock_payment_service
):
    checkout_service.checkout(cart, payment)

    # fragile: breaks on any rename
    mock_payment_service.process.assert_called_once_with(cart.total)
```

Red flags:

- Mocking internal collaborators (things owned by the same module)
- Testing private methods (via name mangling or direct access)
- Asserting on call counts/order rather than outcomes
- Test breaks on refactor without any behavior change
- Test name describes HOW not WHAT

```python
# BAD: Bypasses public interface to verify
def test_create_user_saves_to_database(user_service, db_session):
    user_service.create_user(CreateUserRequest(name="Alice"))

    row = db_session.execute(
        text("SELECT * FROM users WHERE name = :name"),
        {"name": "Alice"},
    ).fetchone()
    assert row is not None


# GOOD: Verifies through the public interface
def test_create_user_makes_user_retrievable(user_service):
    request = CreateUserRequest(name="Alice")

    created = user_service.create_user(request)
    retrieved = user_service.get_user(created.id)

    assert retrieved.name == "Alice"
```

## Naming

Use descriptive function names that convey the scenario:

```python
def test_returns_none_when_product_is_out_of_stock():
    ...
```

Use classes to group related scenarios:

```python
class TestWhenCartIsEmpty:
    def test_checkout_raises_validation_error(self):
        ...

    def test_total_is_zero(self):
        ...
```

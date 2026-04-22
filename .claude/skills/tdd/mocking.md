# Mocking Guidelines

**Rule**: Mock boundaries you don't own — external services, third-party clients, databases in unit tests. Do **not** mock classes you own within the same module.

The rule is the same for Python and TypeScript — only the tools differ.

## unittest.mock / pytest-mock Setup

```python
from unittest.mock import MagicMock

def test_confirms_order_when_payment_succeeds():
    # external boundary
    payment_gateway = MagicMock(spec=PaymentGateway)
    payment_gateway.charge.return_value = PaymentResult.success()

    # class under test
    order_service = OrderService(payment_gateway=payment_gateway)

    result = order_service.place_order(valid_order())

    assert result.status == OrderStatus.CONFIRMED
```

Using `pytest-mock` fixture:

```python
def test_confirms_order_when_payment_succeeds(mocker):
    payment_gateway = mocker.Mock(spec=PaymentGateway)
    payment_gateway.charge.return_value = PaymentResult.success()

    order_service = OrderService(payment_gateway=payment_gateway)

    result = order_service.place_order(valid_order())

    assert result.status == OrderStatus.CONFIRMED
```

## What to Mock

**Python**

| Mock this                             | Don't mock this                        |
|---------------------------------------|----------------------------------------|
| HTTP clients, REST clients            | Your own services and domain logic     |
| Message brokers (Kafka, queues)       | Value objects and dataclasses          |
| External SDKs (payment, email)        | Simple collaborators you can construct |
| Slow I/O in unit tests                | In-memory fakes you can build          |

**TypeScript / React**

| Mock this                             | Don't mock this                        |
|---------------------------------------|----------------------------------------|
| `fetch` / API route calls             | Your own hooks and components          |
| Browser APIs (`window`, `navigator`)  | React context providers you own        |
| Third-party SDKs (analytics, auth)    | Child components under test            |
| `next/router`, `next/navigation`      | Simple state derived from props        |

Use `vi.mock` (Vitest) or `jest.mock` for module-level mocks; use
`msw` (Mock Service Worker) to intercept `fetch` at the network layer
instead of patching `fetch` directly — it's more realistic and
survives implementation changes.

## Avoid Over-Mocking

```python
# BAD: mocking what you own — brittle and hides real logic
def test_registration(mocker):
    mock_repo = mocker.Mock(spec=UserRepository)
    mock_validator = mocker.Mock(spec=EmailValidator)  # your own class!
    service = RegistrationService(mock_repo, mock_validator)

# GOOD: use real collaborators for owned code
def test_registration():
    validator = EmailValidator()
    repo = InMemoryUserRepository()
    service = RegistrationService(repo, validator)
```

## Verify Sparingly

Only assert on interactions that are the **point** of the test, not side effects:

```python
# OK: confirming the side effect IS the behavior being tested
mock_email_service.send_welcome_email.assert_called_once_with(
    user.email
)

# BAD: asserting internal coordination details
mock_user_repo.save.assert_called_once()  # test the outcome, not the call
```

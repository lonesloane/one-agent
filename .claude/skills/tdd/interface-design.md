# Interface Design for Testability

Good interfaces make testing natural:

1. **Accept dependencies via constructor, don't create them**

   Constructor injection makes dependencies explicit and easy to swap in tests.

   ```python
   # Testable: inject the dependency
   class OrderProcessor:
       def __init__(self, gateway: PaymentGateway) -> None:
           self._gateway = gateway

   # Hard to test: creates its own dependency
   class OrderProcessor:
       def process(self, order: Order) -> OrderResult:
           gateway = StripeGateway()  # can't inject a test double
   ```

2. **Return results, don't mutate input or produce hidden side effects**

   ```python
   # Testable: pure computation
   def calculate_discount(cart: Cart) -> Discount:
       ...

   # Hard to test: mutates state, assertion requires side-channel checks
   def apply_discount(cart: Cart) -> None:
       cart.total -= discount
   ```

3. **Prefer immutable return types**

   Use dataclasses or NamedTuples for result objects — they're compact and bring `__eq__` for free:

   ```python
   @dataclass(frozen=True)
   class OrderResult:
       id: OrderId
       status: OrderStatus
   ```

4. **Small surface area**
   - Fewer public methods = fewer tests needed
   - Fewer constructor params = simpler test setup (group related params into a dataclass or config object)

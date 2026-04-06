# Deep Modules

From "A Philosophy of Software Design":

**Deep module** = small interface + lots of implementation

```
┌─────────────────────┐
│   Small Interface   │  <- Few methods, simple params
├─────────────────────┤
│                     │
│                     │
│  Deep Implementation│  <- Complex logic hidden
│                     │
│                     │
└─────────────────────┘
```

**Shallow module** = large interface + little implementation (avoid)

```
┌─────────────────────────────────┐
│       Large Interface           │  <- Many methods, complex params
├─────────────────────────────────┤
│  Thin Implementation            │  <- Just passes through
└─────────────────────────────────┘
```

When designing interfaces, ask:

- Can I reduce the number of methods?
- Can I simplify the parameters? (group with a dataclass)
- Can I hide more complexity inside?

In Python, shallow modules often appear as services that only delegate to a repository with no added logic. If you notice this, either deepen the service (add real behavior) or eliminate the layer and use the repository directly.

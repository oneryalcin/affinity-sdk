# Authentication

The SDK authenticates using an Affinity API key.

```python
from affinity import Affinity

with Affinity(api_key="your-api-key") as client:
    me = client.whoami()
    print(me.user.email)
```

## Environment variables

If you prefer reading from the environment:

```python
from affinity import Affinity

# Reads AFFINITY_API_KEY by default
client = Affinity.from_env()

# Use a custom environment variable name
client = Affinity.from_env(env_var="MY_AFFINITY_KEY")
```

For local development, you can load a `.env` file (requires `python-dotenv`):

```python
from affinity import Affinity

# Load .env from current directory
client = Affinity.from_env(load_dotenv=True)

# Load from a specific path
client = Affinity.from_env(load_dotenv=True, dotenv_path=".env.local")
```

For defensive "no writes" usage (scripts, audits), disable writes via policy:

```python
from affinity import Affinity
from affinity.policies import Policies, WritePolicy

client = Affinity.from_env(policies=Policies(write=WritePolicy.DENY))
```

## CLI Authentication

For the CLI, use the built-in setup commands:

```bash
# Check if a key is configured
xaffinity config check-key

# Set up a new key securely (hidden input)
xaffinity config setup-key
```

See [CLI Authentication](../cli/index.md#authentication) for details.

## Next steps

- [Getting started](../getting-started.md)
- [Configuration](configuration.md)
- [Examples](../examples.md)
- [Errors & retries](errors-and-retries.md)
- [API reference](../reference/client.md)

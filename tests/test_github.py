import pytest

def test_github_client_provider(mocker, isolated_settings):
    mocker.patch("github.client.Github")
    from github.client import GithubClientProvider
    client = GithubClientProvider.get_client()
    assert client is not None

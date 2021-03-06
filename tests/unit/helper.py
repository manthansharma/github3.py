"""Base classes and helpers for unit tests."""
try:
    from unittest import mock
except ImportError:
    import mock
import github3
import json
import os.path
import pytest
import unittest


def create_url_helper(base_url):
    """A function to generate ``url_for`` helpers."""
    base_url = base_url.rstrip('/')

    def url_for(path=''):
        if path:
            path = '/' + path.strip('/')
        return base_url + path

    return url_for


def create_example_data_helper(example_filename):
    """A function to generate example data helpers."""
    directory = os.path.dirname(__file__)
    directory = os.path.join(directory, "json")
    example = os.path.join(directory, example_filename)

    def data_helper():
        with open(example) as fd:
            data = json.load(fd)
        return data

    return data_helper


def build_url(self, *args, **kwargs):
    """A function to proxy to the actual GitHubSession#build_url method."""
    # We want to assert what is happening with the actual calls to the
    # Internet. We can proxy this.
    return github3.session.GitHubSession().build_url(*args, **kwargs)


class UnitHelper(unittest.TestCase):

    """Base class for unittests."""

    # Sub-classes must assign the class to this during definition
    described_class = None
    # Sub-classes must also assign a dictionary to this during definition
    example_data = {}

    def create_mocked_session(self):
        """Use mock to auto-spec a GitHubSession and return an instance."""
        MockedSession = mock.create_autospec(github3.session.GitHubSession)
        return MockedSession()

    def create_session_mock(self, *args):
        """Create a mocked session and add headers and auth attributes."""
        session = self.create_mocked_session()
        base_attrs = ['headers', 'auth']
        attrs = dict(
            (key, mock.Mock()) for key in set(args).union(base_attrs)
        )
        session.configure_mock(**attrs)
        session.delete.return_value = None
        session.get.return_value = None
        session.patch.return_value = None
        session.post.return_value = None
        session.put.return_value = None
        session.has_auth.return_value = True
        return session

    def create_instance_of_described_class(self):
        """
        Use cls.example_data to create an instance of the described class.

        If cls.example_data is None, just create a simple instance of the
        class.
        """
        if self.example_data and self.session:
            instance = self.described_class(self.example_data,
                                            self.session)
        elif self.example_data and not self.session:
            instance = self.described_class(self.example_data)

        else:
            instance = self.described_class()
            instance.session = self.session

        return instance

    def delete_called_with(self, *args, **kwargs):
        """Use to assert delete was called with JSON."""
        self.method_called_with('delete', args, kwargs)

    def method_called_with(self, method_name, args, kwargs):
        """Assert that a method was called on a session with JSON."""
        mock_method = getattr(self.session, method_name)
        assert mock_method.called is True
        call_args, call_kwargs = mock_method.call_args

        # Data passed to assertion
        data = kwargs.pop('data', None)
        # Data passed to patch
        call_data = call_kwargs.pop('data', None)
        # Data passed by the call to post positionally
        #                                URL, 'json string'
        if call_data is None:
            call_args, call_data = call_args[:1], call_args[1]
        # If data is a dictionary (or list) and call_data exists
        if not isinstance(data, str) and call_data:
            call_data = json.loads(call_data)

        assert args == call_args
        assert data == call_data
        assert kwargs == call_kwargs

    def patch_called_with(self, *args, **kwargs):
        """Use to assert patch was called with JSON."""
        self.method_called_with('patch', args, kwargs)

    def post_called_with(self, *args, **kwargs):
        """Use to assert post was called with JSON."""
        assert self.session.post.called is True
        call_args, call_kwargs = self.session.post.call_args

        # Data passed to assertion
        data = kwargs.pop('data', None)
        # Data passed by the call to post positionally
        #                                URL, 'json string'
        call_args, call_data = call_args[:1], call_args[1]
        # If data is a dictionary (or list) and call_data exists
        if not isinstance(data, str) and call_data:
            call_data = json.loads(call_data)

        assert args == call_args
        assert data == call_data
        assert kwargs == call_kwargs

    def put_called_with(self, *args, **kwargs):
        """Use to assert put was called with JSON."""
        self.method_called_with('put', args, kwargs)

    def setUp(self):
        """Use to set up attributes on self before each test."""
        self.session = self.create_session_mock()
        self.instance = self.create_instance_of_described_class()
        # Proxy the build_url method to the class so it can build the URL and
        # we can assert things about the call that will be attempted to the
        # internet
        self.described_class._build_url = build_url
        self.after_setup()

    def after_setup(self):
        """No-op method to avoid people having to override setUp."""
        pass


class UnitIteratorHelper(UnitHelper):

    """Base class for iterator based unit tests."""

    def create_session_mock(self, *args):
        """Override UnitHelper's create_session_mock method.

        We want all methods to return an instance of the NullObject. This
        class has a dummy ``__iter__`` implementation which we want for
        methods that iterate over the results of a response.
        """
        # Retrieve a mocked session object
        session = super(UnitIteratorHelper, self).create_mocked_session(*args)
        # Initialize a NullObject which has magical properties
        null = github3.null.NullObject()
        # Set it as the return value for every method
        session.delete.return_value = null
        session.get.return_value = null
        session.patch.return_value = null
        session.post.return_value = null
        session.put.return_value = null
        return session

    def get_next(self, iterator):
        """Nicely wrap up a call to the iterator."""
        try:
            next(iterator)
        except StopIteration:
            pass

    def patch_get_json(self):
        """Patch a GitHubIterator's _get_json method."""
        self.get_json_mock = mock.patch.object(
            github3.structs.GitHubIterator, '_get_json'
        )
        self.patched_get_json = self.get_json_mock.start()
        self.patched_get_json.return_value = []

    def setUp(self):
        """Use UnitHelper's setUp but also patch _get_json."""
        super(UnitIteratorHelper, self).setUp()
        self.patch_get_json()

    def tearDown(self):
        """Stop mocking _get_json."""
        super(UnitIteratorHelper, self).tearDown()
        self.get_json_mock.stop()


class UnitRequiresAuthenticationHelper(UnitHelper):

    """Helper for unit tests that demonstrate authentication is required."""

    def after_setup(self):
        """Disable authentication on the session."""
        self.session.auth = None
        self.session.has_auth.return_value = False

    def assert_requires_auth(self, func, *args, **kwargs):
        """
        Assert error is raised if function is called without
        authentication.
        """
        with pytest.raises(github3.exceptions.AuthenticationFailed):
            func(*args, **kwargs)


class UnitGitHubObjectHelper(UnitHelper):

    """Base class for GitHubObject unit tests."""

    def setUp(self):
        self.session = None
        self.instance = self.create_instance_of_described_class()
        # Proxy the build_url method to the class so it can build the URL and
        # we can assert things about the call that will be attempted to the
        # internet
        self.described_class._build_url = build_url
        self.after_setup()
        pass


@pytest.mark.usefixtures('enterprise_url')
class UnitGitHubEnterpriseHelper(UnitHelper):

    def build_url(self, *args, **kwargs):
        """A function to proxy to the actual GitHubSession#build_url method."""
        # We want to assert what is happening with the actual calls to the
        # Internet. We can proxy this.
        return github3.session.GitHubSession().build_url(
            *args,
            base_url=self.enterprise_url,
            **kwargs
        )

    def setUp(self):
        self.session = self.create_session_mock()
        self.instance = github3.GitHubEnterprise(self.enterprise_url)
        self.instance.session = self.session
        # Proxy the build_url method to the class so it can build the URL and
        # we can assert things about the call that will be attempted to the
        # internet
        self.instance._build_url = self.build_url
        self.after_setup()

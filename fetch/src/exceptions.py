class DataServiceError(Exception):
    """Base exception for Data Service errors."""
    pass

class FetcherError(DataServiceError):
    """Raised when an error occurs during data fetching."""
    pass

class StorageError(DataServiceError):
    """Raised when an error occurs during file storage/retrieval."""
    pass

class InvalidParameterError(DataServiceError):
    """Raised when invalid parameters are provided."""
    pass

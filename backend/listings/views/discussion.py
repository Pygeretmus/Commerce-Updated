from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from configuration.pagination import StandardPagination

from ..models import Comment, Listing
from ..serializers import CommentCreateSerializer, CommentSerializer
from ..services.discussion import delete_comment, post_comment


def public_listing(pk: int) -> Listing:
    """Drafts do not exist for anyone but their seller, and the seller cannot discuss or watch them."""
    return get_object_or_404(Listing.objects.exclude(status=Listing.Status.DRAFT), pk=pk)


@extend_schema_view(
    get=extend_schema(responses=CommentSerializer(many=True)),
    post=extend_schema(request=CommentCreateSerializer, responses={201: CommentSerializer}),
)
class CommentListCreateView(ListCreateAPIView):
    """Questions and answers under a lot, oldest first. The seller's comments are marked `is_seller`."""

    pagination_class = StandardPagination
    serializer_class = CommentSerializer
    throttle_scope = 'comment'
    permission_classes = (IsAuthenticatedOrReadOnly,)

    @cached_property
    def listing(self) -> Listing:
        return public_listing(self.kwargs['pk'])

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'listing': self.listing}

    def get_queryset(self):
        return Comment.objects.filter(listing=self.listing, deleted_at__isnull=True).select_related('author')

    def create(self, request, *args, **kwargs):
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = post_comment(self.listing, request.user, serializer.validated_data['body'])
        return Response(
            CommentSerializer(comment, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED
        )


@extend_schema(responses={204: None})
class CommentDestroyView(GenericAPIView):
    """Removes my own comment (it is only hidden, not erased)."""

    serializer_class = CommentSerializer

    def delete(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs['pk'], deleted_at__isnull=True)
        delete_comment(comment, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

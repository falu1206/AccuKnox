from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, FriendRequest, Friendship
from .serializers import UserSerializer, FriendRequestSerializer, FriendshipSerializer
from django.core.paginator import Paginator

class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = User.objects.get(email__iexact=email)
        if user and user.check_password(password):
            return Response({'token': user.auth_token.key})
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class SignupView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(email, email, request.data.get('password'))
        return Response({'token': user.auth_token.key})

class SearchUserView(APIView):
    def get(self, request):
        search_keyword = request.GET.get('search')
        users = User.objects.all()
        if '@' in search_keyword:
            users = users.filter(email__iexact=search_keyword)
        else:
            users = users.filter(username__icontains=search_keyword)
        paginator = Paginator(users, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        serializer = UserSerializer(page_obj.object_list, many=True)
        return Response(serializer.data)

class SendFriendRequestView(APIView):
    def post(self, request):
        sender = request.user
        receiver_email = request.data.get('email')
        receiver = User.objects.get(email__iexact=receiver_email)
        if sender == receiver:
            return Response({'error': 'Cannot send friend request to yourself'}, status=status.HTTP_400_BAD_REQUEST)
        if FriendRequest.objects.filter(sender=sender, receiver=receiver).exists():
            return Response({'error': 'Friend request already sent'}, status=status.HTTP_400_BAD_REQUEST)
        if sender.sent_friend_requests.count() >= 3 and (datetime.now() - sender.sent_friend_requests.latest('created_at').created_at).total_seconds() < 60:
            return Response({'error': 'Too many friend requests sent in the last minute'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        friend_request = FriendRequest.objects.create(sender=sender, receiver=receiver)
        return Response({'id': friend_request.id})

class AcceptFriendRequestView(APIView):
    def post(self, request, pk):
        friend_request = FriendRequest.objects.get(pk=pk)
        if friend_request.receiver != request.user:
            return Response({'error': 'You are not the intended recipient of this friend request'}, status=status.HTTP_403_FORBIDDEN)
        friend_request.status = 'accepted'
        friend_request.save()
        Friendship.objects.create(user1=friend_request.sender, user2=friend_request.receiver)
        return Response({'message': 'Friend request accepted'})

class RejectFriendRequestView(APIView):
    def post(self, request, pk):
        friend_request = FriendRequest.objects.get(pk=pk)
        if friend_request.receiver != request.user:
            return Response({'error': 'You are not the intended recipient of this friend request'}, status=status.HTTP_403_FORBIDDEN)
        friend_request.status = 'rejected'
        friend_request.save()
        return Response({'message': 'Friend request rejected'})

class ListFriendsView(APIView):
    def get(self, request):
        user = request.user
        friendships = Friendship.objects.filter(user1=user) | Friendship.objects.filter(user2=user)
        serializer = FriendshipSerializer(friendships, many=True)
        return Response([friendship['user2'] if friendship['user1'] == user else friendship['user1'] for friendship in serializer.data])

class ListPendingFriendRequestsView(APIView):
    def get(self, request):
        user = request.user
        friend_requests = FriendRequest.objects.filter(receiver=user, status='pending')
        serializer = FriendRequestSerializer(friend_requests, many=True)
        return Response(serializer.data)
    
    
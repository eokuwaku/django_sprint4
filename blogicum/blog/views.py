from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import CommentForm, PostForm, ProfileEditForm
from .models import Category, Comment, Post

User = get_user_model()


class AuthorRequiredMixin:
    """Проверяет, что текущий пользователь — автор объекта."""

    def post(self, request, *args, **kwargs):
        if self.get_object().author != request.user:
            raise Http404
        return super().post(request, *args, **kwargs)


class CommentFormMixin:
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'


class PostMixin:
    model = Post
    template_name = 'blog/create.html'


class IndexListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = 10
    ordering = '-pub_date'
    queryset = (
        Post.objects.select_related('location', 'category', 'author')
        .filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
        .annotate(comment_count=Count('comments'))
    )


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if not (
            post.is_published
            and post.pub_date <= timezone.now()
            and post.category.is_published
        ) and (request.user != post.author):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['comments'] = self.object.comments.select_related('author')
        return context


def category_posts(request, category_slug):
    template_name = 'blog/category.html'
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    post_list = (
        category.posts.all()
        .select_related('location', 'author')
        .filter(is_published=True, pub_date__lte=timezone.now())
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date')
    )
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page', 0)
    page_obj = paginator.get_page(page_number)
    context = {
        'page_obj': page_obj,
        'category': category,
    }
    return render(request, template_name, context)


def profile(request, username):
    template_name = 'blog/profile.html'
    user = get_object_or_404(User, username=username)
    posts = (
        Post.objects.filter(author=user)
        .select_related('author', 'location', 'category')
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date')
    )
    if request.user != user:
        posts = posts.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    context = {'profile': user, 'page_obj': page_obj}
    return render(request, template_name, context)


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileEditForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile', kwargs={'username': self.object.username}
        )


class PostCreateView(PostMixin, LoginRequiredMixin, CreateView):
    form_class = PostForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile', kwargs={'username': self.object.author.username}
        )


class PostEditView(PostMixin, UpdateView):
    form_class = PostForm

    def post(self, request, *args, **kwargs):
        if (
            not request.user.is_authenticated
            or self.get_object().author != request.user
        ):
            return redirect('blog:post_detail', pk=kwargs.get('pk'))
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'pk': self.object.id})


class PostDeleteView(
    PostMixin, LoginRequiredMixin, AuthorRequiredMixin, DeleteView
):
    success_url = reverse_lazy('blog:index')


class CommentCreateView(CommentFormMixin, LoginRequiredMixin, CreateView):
    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = get_object_or_404(Post, pk=self.kwargs['pk'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'pk': self.kwargs['pk']})


class CommentEditView(
    CommentFormMixin, LoginRequiredMixin, AuthorRequiredMixin, UpdateView
):
    pk_url_kwarg = 'comment_id'

    def get_success_url(self):
        return reverse(
            'blog:post_detail', kwargs={'pk': self.kwargs['post_id']}
        )


class CommentDeleteView(LoginRequiredMixin, AuthorRequiredMixin, DeleteView):
    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def get_success_url(self):
        return reverse(
            'blog:post_detail', kwargs={'pk': self.kwargs['post_id']}
        )

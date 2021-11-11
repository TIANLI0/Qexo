# -*- encoding: utf-8 -*-
import requests
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from .forms import LoginForm
from django import template
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.template import loader
from core.settings import QEXO_VERSION
import github
from django.template.defaulttags import register
import json
from .models import Cache, SettingModel, ImageModel
import time
import random


def get_repo():
    if SettingModel.objects.filter(name__contains="GH_").count() >= 4:
        repo = github.Github(SettingModel.objects.get(name='GH_TOKEN').content).get_repo(
            SettingModel.objects.get(name="GH_REPO").content)
        return repo
    return False


@register.filter  # 在模板中使用range()
def get_range(value):
    return range(1, value + 1)


@register.filter
def div(value, div):  # 保留两位小数的除法
    return round((value / div), 2)


# 更新缓存
def update_caches(name, content, _type="json"):
    caches = Cache.objects.filter(name=name)
    if caches.count():
        caches.delete()
    posts_cache = Cache()
    posts_cache.name = name
    if _type == "json":
        posts_cache.content = json.dumps(content)
    else:
        posts_cache.content = content
    posts_cache.save()


def update_posts_cache(s=None):
    repo = get_repo()
    posts = repo.get_contents(
        SettingModel.objects.get(name="GH_REPO_PATH").content + 'source/_posts',
        ref=SettingModel.objects.get(name="GH_REPO_BRANCH").content)
    for i in range(len(posts)):
        posts[i] = {"name": posts[i].name[0:-3], "path": posts[i].path, "size": posts[i].size,
                    "status": True}
    try:
        drafts = repo.get_contents(
            SettingModel.objects.get(name="GH_REPO_PATH").content + 'source/_drafts',
            ref=SettingModel.objects.get(name="GH_REPO_BRANCH").content)
        for i in range(len(drafts)):
            drafts[i] = {"name": drafts[i].name[0:-3], "path": drafts[i].path,
                         "size": drafts[i].size, "status": False}
        posts = posts + drafts
    except:
        pass
    if s:
        i = 0
        while i < len(posts):
            if s not in posts[i]["name"]:
                del posts[i]
                i -= 1
            i += 1
    if s:
        cache_name = "posts." + str(s)
    else:
        cache_name = "posts"

    update_caches(cache_name, posts)
    return posts


def update_pages_cache(s=None):
    repo = get_repo()
    posts = repo.get_contents(SettingModel.objects.get(name="GH_REPO_PATH").content + 'source',
                              ref=SettingModel.objects.get(name="GH_REPO_BRANCH").content)
    results = list()
    for post in posts:
        if post.type == "dir":
            for i in repo.get_contents(
                    SettingModel.objects.get(name="GH_REPO_PATH").content + post.path,
                    ref=SettingModel.objects.get(name="GH_REPO_BRANCH").content):
                if i.type == "file":
                    if s:
                        if (i.name == "index.md" or i.name == "index.html") and (
                                str(s) in post.name):
                            results.append({"name": post.name, "path": i.path, "size": i.size})
                            break
                    else:
                        if i.name == "index.md" or i.name == "index.html":
                            results.append({"name": post.name, "path": i.path, "size": i.size})
                            break
    if s:
        cache_name = "pages." + str(s)
    else:
        cache_name = "pages"
    update_caches(cache_name, results)
    return results


def delete_all_caches():
    caches = Cache.objects.all()
    for cache in caches:
        cache.delete()


def delete_posts_caches():
    caches = Cache.objects.all()
    for cache in caches:
        if cache.name[:5] == "posts":
            cache.delete()


def delete_pages_caches():
    caches = Cache.objects.all()
    for cache in caches:
        try:
            name = cache.name[:5]
        except:
            name = ""
        if name == "pages":
            cache.delete()


def save_setting(name, content):
    obj = SettingModel.objects.filter(name=name)
    if obj.count() == 1:
        obj.delete()
    if obj.count() > 1:
        for i in obj:
            i.delete()
    new_set = SettingModel()
    new_set.name = str(name)
    if content is not None:
        new_set.content = str(content)
    else:
        new_set.content = ""
    new_set.save()
    return new_set


def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None
    try:
        if int(SettingModel.objects.get(name="INIT").content) <= 5:
            return redirect("/init/")
    except:
        return redirect("/init/")
    if request.method == "POST":

        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if request.GET.get("next"):
                    return redirect(request.GET.get("next"))
                return redirect("/")
            else:
                msg = '登录信息错误'
        else:
            msg = '验证表单时出错'

    return render(request, "accounts/login.html", {"form": form, "msg": msg})


def init_view(request):
    msg = None
    context = dict()
    try:
        step = SettingModel.objects.get(name="INIT").content
    except:
        save_setting("INIT", "1")
        step = "1"

    if request.method == "POST":
        if request.POST.get("step") == "1":
            save_setting("INIT", "2")
            step = "2"
        if request.POST.get("step") == "2":
            try:
                username = request.POST.get("username")
                password = request.POST.get("password")
                repassword = request.POST.get("repassword")
                if repassword != password:
                    msg = "两次密码不一致!"
                    context["username"] = username
                    context["password"] = password
                    context["repassword"] = repassword
                elif not password:
                    msg = "请输入正确的密码！"
                    context["username"] = username
                    context["password"] = password
                    context["repassword"] = repassword
                elif not username:
                    msg = "请输入正确的用户名！"
                    context["username"] = username
                    context["password"] = password
                    context["repassword"] = repassword
                else:
                    User.objects.create_superuser(username=username, password=password)
                    save_setting("INIT", "3")
                    step = "3"
            except Exception as e:
                msg = repr(e)
                context["username"] = username
                context["password"] = password
                context["repassword"] = repassword
        if request.POST.get("step") == "3":
            try:
                repo = request.POST.get("repo")
                branch = request.POST.get("branch")
                token = request.POST.get("token")
                path = request.POST.get("path")
                try:
                    _repo = github.Github(token).get_repo(repo).get_contents(path + "source/_posts",
                                                                             ref=branch)
                    save_setting("GH_REPO_PATH", path)
                    save_setting("GH_REPO_BRANCH", branch)
                    save_setting("GH_REPO", repo)
                    save_setting("GH_TOKEN", token)
                    save_setting("INIT", "4")
                    step = "4"
                except:
                    msg = "校验失败"
                    context["repo"] = repo
                    context["branch"] = branch
                    context["token"] = token
                    context["path"] = path
            except Exception as e:
                msg = repr(e)
                context["repo"] = repo
                context["branch"] = branch
                context["token"] = token
                context["path"] = path
        if request.POST.get("step") == "4":
            api = request.POST.get("api")
            post_params = request.POST.get("post")
            json_path = request.POST.get("jsonpath")
            custom_body = request.POST.get("body")
            custom_header = request.POST.get("header")
            custom_url = request.POST.get("custom")
            try:
                save_setting("IMG_API", api)
                save_setting("IMG_POST", post_params)
                save_setting("IMG_JSON_PATH", json_path)
                save_setting("IMG_CUSTOM_BODY", custom_body)
                save_setting("IMG_CUSTOM_HEADER", custom_header)
                save_setting("IMG_CUSTOM_URL", custom_url)
                save_setting("INIT", "6")
                step = "5"
            except Exception as e:
                msg = repr(e)
                context["api"] = api
                context["post"] = post_params
                context["jsonpath"] = json_path
                context["body"] = custom_body
                context["header"] = custom_header
                context["custom"] = custom_url
        if step == "5":
            user = User.objects.all()[0]
            context["username"] = user.username
    elif int(step) >= 5:
        return redirect("/")
    return render(request, "accounts/init.html", {"msg": msg, "step": step, "context": context})


def logout_view(request):
    logout(request)
    return redirect('/login/?next=/')


# API
@login_required(login_url="/login/")
def set_github(request):
    try:
        repo = request.POST.get("repo")
        branch = request.POST.get("branch")
        token = request.POST.get("token")
        path = request.POST.get("path")
        try:
            _repo = github.Github(token).get_repo(repo).get_contents(path + "source/_posts",
                                                                     ref=branch)
            save_setting("GH_REPO_PATH", path)
            save_setting("GH_REPO_BRANCH", branch)
            save_setting("GH_REPO", repo)
            save_setting("GH_TOKEN", token)
            context = {"msg": "保存成功!", "status": True}
        except:
            context = {"msg": "校验失败!", "status": False}
    except Exception as e:
        context = {"msg": repr(e), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def set_webhook(request):
    try:
        apikey = request.POST.get("apikey")
        save_setting("WEBHOOK_APIKEY", apikey)
        context = {"msg": "保存成功!", "status": True}
    except Exception as e:
        context = {"msg": repr(e), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def set_image_bed(request):
    try:
        api = request.POST.get("api")
        post_params = request.POST.get("post")
        json_path = request.POST.get("jsonpath")
        custom_body = request.POST.get("body")
        custom_header = request.POST.get("header")
        custom_url = request.POST.get("custom")
        save_setting("IMG_API", api)
        save_setting("IMG_POST", post_params)
        save_setting("IMG_JSON_PATH", json_path)
        save_setting("IMG_CUSTOM_BODY", custom_body)
        save_setting("IMG_CUSTOM_HEADER", custom_header)
        save_setting("IMG_CUSTOM_URL", custom_url)
        context = {"msg": "保存成功!", "status": True}
    except Exception as e:
        context = {"msg": repr(e), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def set_user(request):
    try:
        password = request.POST.get("password")
        username = request.POST.get("username")
        newpassword = request.POST.get("newpassword")
        repassword = request.POST.get("repassword")
        user = authenticate(username=request.user.username, password=password)
        if user is not None:
            if repassword != newpassword:
                context = {"msg": "两次密码不一致!", "status": False}
                return render(request, 'layouts/json.html', {"data": json.dumps(context)})
            if not newpassword:
                context = {"msg": "请输入正确的密码！", "status": False}
                return render(request, 'layouts/json.html', {"data": json.dumps(context)})
            if not username:
                context = {"msg": "请输入正确的用户名！", "status": False}
                return render(request, 'layouts/json.html', {"data": json.dumps(context)})
            u = User.objects.get(username__exact=request.user.username)
            u.delete()
            User.objects.create_superuser(username=username, password=newpassword)
            context = {"msg": "保存成功！请重新登录", "status": True}
        else:
            context = {"msg": "原密码错误!", "status": False}
    except Exception as e:
        context = {"msg": repr(e), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def save(request):
    repo = get_repo()
    context = dict(msg="Error!", status=False)
    if request.method == "POST":
        file_path = request.POST.get('file')
        content = request.POST.get('content')
        try:
            repo.update_file(SettingModel.objects.get(name="GH_REPO_PATH").content + file_path,
                             "Update by Qexo", content, repo.get_contents(
                    SettingModel.objects.get(name="GH_REPO_PATH").content + file_path,
                    ref=SettingModel.objects.get(name="GH_REPO_BRANCH").content).sha,
                             branch=SettingModel.objects.get(name="GH_REPO_BRANCH").content)
            context = {"msg": "OK!", "status": True}
        except Exception as error:
            context = {"msg": repr(error), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def new(request):
    repo = get_repo()
    context = dict(msg="Error!", status=False)
    if request.method == "POST":
        file_path = request.POST.get('file')
        content = request.POST.get('content')
        try:
            repo.create_file(path=SettingModel.objects.get(name="GH_REPO_PATH").content + file_path,
                             message="Create by Qexo", content=content,
                             branch=SettingModel.objects.get(name="GH_REPO_BRANCH").content)
            context = {"msg": "OK!", "status": True}
        except Exception as error:
            context = {"msg": repr(error), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def delete(request):
    repo = get_repo()
    context = dict(msg="Error!", status=False)
    if request.method == "POST":
        file_path = request.POST.get('file')
        try:
            file = repo.get_contents(file_path,
                                     ref=SettingModel.objects.get(
                                         name="GH_REPO_BRANCH").content)
            if not isinstance(file, list):
                repo.delete_file(SettingModel.objects.get(name="GH_REPO_PATH").content + file_path,
                                 "Delete by Qexo", file.sha,
                                 branch=SettingModel.objects.get(name="GH_REPO_BRANCH").content)

            else:
                for i in file:
                    repo.delete_file(
                        SettingModel.objects.get(name="GH_REPO_PATH").content + i.path,
                        "Delete by Qexo", i.sha,
                        branch=SettingModel.objects.get(name="GH_REPO_BRANCH").content)
            context = {"msg": "OK!", "status": True}
            # Delete Caches
            if ("_posts" in file_path) or ("_drafts" in file_path):
                delete_posts_caches()
            else:
                delete_all_caches()
        except Exception as error:
            context = {"msg": repr(error)}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def delete_img(request):
    context = dict(msg="Error!", status=False)
    if request.method == "POST":
        image_date = request.POST.get('image')
        try:
            image = ImageModel.objects.get(date=image_date)
            image.delete()
            context = {"msg": "删除成功！", "status": True}
        except Exception as error:
            context = {"msg": repr(error), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def purge(request):
    context = dict(msg="Error!", status=False)
    try:
        delete_all_caches()
        context = {"msg": "清除成功！", "status": True}
    except Exception as error:
        context = {"msg": repr(error), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@login_required(login_url="/login/")
def create_webhook_config(request):
    context = dict(msg="Error!", status=False)
    if request.method == "POST":
        try:
            if SettingModel.objects.filter(name="WEBHOOK_APIKEY"):
                config = {
                    "content_type": "json",
                    "url": request.POST.get("uri") + "?token=" + SettingModel.objects.get(
                        name="WEBHOOK_APIKEY").content
                }
            else:
                save_setting("WEBHOOK_APIKEY", ''.join(
                    random.choice("qwertyuiopasdfghjklzxcvbnm1234567890") for x in range(12)))
                config = {
                    "content_type": "json",
                    "url": request.POST.get("uri") + "?token=" + SettingModel.objects.get(
                        name="WEBHOOK_APIKEY").content
                }
            repo = get_repo()
            for hook in repo.get_hooks():  # 删除所有HOOK
                hook.delete()
            repo.create_hook(active=True, config=config, events=["push"], name="web")
            context = {"msg": "设置成功！", "status": True}
        except Exception as error:
            context = {"msg": repr(error), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@csrf_exempt
def webhook(request):
    context = dict(msg="Error!", status=False)
    try:
        if request.GET.get("token") == SettingModel.objects.get(name="WEBHOOK_APIKEY").content:
            delete_all_caches()
            context = {"msg": "操作成功！", "status": True}
        else:
            context = {"msg": "校验错误", "status": False}
    except Exception as error:
        context = {"msg": repr(error), "status": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


@csrf_exempt
@login_required(login_url="/login/")
def upload_img(request):
    context = dict(msg="上传失败！", url=False)
    if request.method == "POST":
        file = request.FILES.getlist('file[]')[0]
        try:
            api = SettingModel.objects.get(name="IMG_API").content
            post_params = SettingModel.objects.get(name="IMG_POST").content
            json_path = SettingModel.objects.get(name="IMG_JSON_PATH").content
            custom_body = SettingModel.objects.get(name="IMG_CUSTOM_BODY").content
            custom_header = SettingModel.objects.get(name="IMG_CUSTOM_HEADER").content
            custom_url = SettingModel.objects.get(name="IMG_CUSTOM_URL").content
            if custom_header:
                if custom_body:
                    response = requests.post(api, data=json.loads(custom_body),
                                             headers=json.loads(custom_header),
                                             files={post_params: [file.name, file.read(),
                                                                  file.content_type]})
                else:
                    response = requests.post(api, data={}, headers=json.loads(custom_header),
                                             files={post_params: [file.name, file.read(),
                                                                  file.content_type]})
            else:
                if custom_body:
                    response = requests.post(api, data=json.loads(custom_body),
                                             files={post_params: [file.name, file.read(),
                                                                  file.content_type]})
                else:
                    response = requests.post(api, data={},
                                             files={post_params: [file.name, file.read(),
                                                                  file.content_type]})
            if json_path:
                json_path = json_path.split(".")
                response.encoding = "utf8"
                data = response.json()
                for path in json_path:
                    data = data[path]
                context["url"] = str(custom_url) + data
                context["msg"] = "上传成功！"
                context["status"] = True
            else:
                context["url"] = str(custom_url) + response.text
                context["msg"] = "上传成功！"
                context["status"] = True
            image = ImageModel()
            image.name = file.name
            image.url = context["url"]
            image.size = file.size
            image.type = file.content_type
            image.date = time.time()
            image.save()
        except Exception as error:
            context = {"msg": repr(error), "url": False}
    return render(request, 'layouts/json.html', {"data": json.dumps(context)})


# Pages
@login_required(login_url="/login/")
def index(request):
    try:
        if int(SettingModel.objects.get(name="INIT").content) <= 5:
            return redirect("/init/")
    except:
        return redirect("/init/")
    context = {'segment': 'index'}
    cache = Cache.objects.filter(name="posts")
    if cache.count():
        posts = json.loads(cache.first().content)
    else:
        posts = update_posts_cache()
    _images = ImageModel.objects.all()
    images = list()
    for i in _images:
        images.append({"name": i.name, "size": int(i.size), "url": i.url,
                       "date": time.strftime("%Y-%m-%d", time.localtime(float(i.date)))})
    if len(posts) >= 5:
        context["posts"] = posts[0:5]
    else:
        context["posts"] = posts
    if len(images) >= 5:
        context["images"] = images[0:5]
    else:
        context["images"] = images
    context["version"] = QEXO_VERSION
    context["post_number"] = str(len(posts))
    context["images_number"] = str(len(images))
    context["github_dev"] = "https://github.dev/" + SettingModel.objects.get(
        name="GH_REPO").content + "/tree/" + SettingModel.objects.get(name="GH_REPO_BRANCH").content
    html_template = loader.get_template('home/index.html')
    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/login/")
def pages(request):
    context = dict()
    try:
        if int(SettingModel.objects.get(name="INIT").content) <= 5:
            return redirect("/init/")
    except:
        pass
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:
        load_template = request.path.split('/')[-1]
        context['segment'] = load_template
        if "edit_page" in load_template:
            repo = get_repo()
            file_path = request.GET.get("file")
            context["file_content"] = repr(
                repo.get_contents(SettingModel.objects.get(name="GH_REPO_PATH").content + file_path,
                                  ref=SettingModel.objects.get(
                                      name="GH_REPO_BRANCH").content).decoded_content.decode(
                    "utf8"))
            context['filename'] = file_path.split("/")[-2] + "/" + file_path.split("/")[-1]
            context["file_path"] = file_path
            try:
                if SettingModel.objects.get(name="IMG_API").content and SettingModel.objects.get(
                        name="IMG_POST").content:
                    context["img_bed"] = True
            except:
                pass
        elif "edit" in load_template:
            repo = get_repo()
            file_path = request.GET.get("file")
            context["file_content"] = repr(
                repo.get_contents(SettingModel.objects.get(name="GH_REPO_PATH").content + file_path,
                                  ref=SettingModel.objects.get(
                                      name="GH_REPO_BRANCH").content).decoded_content.decode(
                    "utf8"))
            context['filename'] = file_path.split("/")[-1]
            context["file_path"] = file_path
            try:
                if SettingModel.objects.get(name="IMG_API").content and SettingModel.objects.get(
                        name="IMG_POST").content:
                    context["img_bed"] = True
            except:
                pass
        elif "new_page" in load_template:
            repo = get_repo()
            try:
                context["file_content"] = repr(
                    repo.get_contents(
                        SettingModel.objects.get(name="GH_REPO_PATH").content + "scaffolds/page.md",
                        ref=SettingModel.objects.get(
                            name="GH_REPO_BRANCH").content).decoded_content.decode(
                        "utf8"))
            except:
                pass
            try:
                if SettingModel.objects.get(name="IMG_API").content and SettingModel.objects.get(
                        name="IMG_POST").content:
                    context["img_bed"] = True
            except:
                pass
        elif "new" in load_template:
            repo = get_repo()
            try:
                context["file_content"] = repr(
                    repo.get_contents(
                        SettingModel.objects.get(name="GH_REPO_PATH").content + "scaffolds/post.md",
                        ref=SettingModel.objects.get(
                            name="GH_REPO_BRANCH").content).decoded_content.decode(
                        "utf8"))
            except:
                pass
            try:
                if SettingModel.objects.get(name="IMG_API").content and SettingModel.objects.get(
                        name="IMG_POST").content:
                    context["img_bed"] = True
            except:
                pass
        elif "posts" in load_template:
            page = request.GET.get("page")
            search = request.GET.get("s")
            if search:
                cache = Cache.objects.filter(name="posts." + search)
                if cache.count():
                    posts = json.loads(cache.first().content)
                else:
                    posts = update_posts_cache(search)
            else:
                cache = Cache.objects.filter(name="posts")
                if cache.count():
                    posts = json.loads(cache.first().content)
                else:
                    posts = update_posts_cache(search)
            if not page:
                page = 1
            if int(page) == 1:
                context["start"] = True
            if len(posts) <= 15:
                context["posts"] = posts
                context["end"] = True
            else:
                page = int(page)
                try:
                    posts[page * 15 + 1]
                except:
                    context["end"] = True
                context["posts"] = posts[15 * (page - 1):page * 15]
            context["page"] = page
            context["post_number"] = len(posts)
            context["page_number"] = context["post_number"] // 15 + 1
            context["search"] = search
        elif "pages" in load_template:
            search = request.GET.get("s")
            if search:
                cache = Cache.objects.filter(name="pages." + search)
                if cache.count():
                    posts = json.loads(cache.first().content)
                else:
                    posts = update_pages_cache(search)
            else:
                cache = Cache.objects.filter(name="pages")
                if cache.count():
                    posts = json.loads(cache.first().content)
                else:
                    posts = update_pages_cache(search)
            context["posts"] = posts
            context["post_number"] = len(posts)
            context["search"] = search
        elif "images" in load_template:
            page = request.GET.get("page")
            search = request.GET.get("s")
            posts = []
            if search:
                images = ImageModel.objects.filter(name__contains=search)
                for i in images:
                    posts.append({"name": i.name, "size": int(i.size), "url": i.url,
                                  "date": time.strftime("%Y-%m-%d %H:%M:%S",
                                                        time.localtime(float(i.date))),
                                  "time": i.date})
            else:
                images = ImageModel.objects.all()
                for i in images:
                    posts.append({"name": i.name, "size": int(i.size), "url": i.url,
                                  "date": time.strftime("%Y-%m-%d %H:%M:%S",
                                                        time.localtime(float(i.date))),
                                  "time": i.date})
            if not page:
                page = 1
            if int(page) == 1:
                context["start"] = True
            if len(posts) <= 15:
                context["posts"] = posts
                context["end"] = True
            else:
                page = int(page)
                try:
                    posts[page * 15 + 1]
                except:
                    context["end"] = True
                context["posts"] = posts[15 * (page - 1):page * 15]
            context["page"] = page
            context["post_number"] = len(posts)
            context["page_number"] = context["post_number"] // 15 + 1
            context["search"] = search
        elif 'settings' in load_template:
            try:
                context['GH_REPO_PATH'] = SettingModel.objects.get(name="GH_REPO_PATH").content
                context['GH_REPO_BRANCH'] = SettingModel.objects.get(name="GH_REPO_BRANCH").content
                context['GH_REPO'] = SettingModel.objects.get(name="GH_REPO").content
                context['GH_TOKEN'] = SettingModel.objects.get(name="GH_TOKEN").content
                context['IMG_CUSTOM_URL'] = SettingModel.objects.get(name='IMG_CUSTOM_URL').content
                context['IMG_CUSTOM_HEADER'] = SettingModel.objects.get(
                    name='IMG_CUSTOM_HEADER').content
                context['IMG_CUSTOM_BODY'] = SettingModel.objects.get(
                    name='IMG_CUSTOM_BODY').content
                context['IMG_JSON_PATH'] = SettingModel.objects.get(name='IMG_JSON_PATH').content
                context['IMG_POST'] = SettingModel.objects.get(name='IMG_POST').content
                context['IMG_API'] = SettingModel.objects.get(name='IMG_API').content
            except Exception as e:
                context["error"] = repr(e)
        context["github_dev"] = "https://github.dev/" + SettingModel.objects.get(
            name="GH_REPO").content + "/tree/" + SettingModel.objects.get(
            name="GH_REPO_BRANCH").content
        html_template = loader.get_template('home/' + load_template)
        return HttpResponse(html_template.render(context, request))

    except template.TemplateDoesNotExist:
        html_template = loader.get_template('home/page-404.html')
        return HttpResponse(html_template.render(context, request))

    except Exception as error:
        html_template = loader.get_template('home/page-500.html')
        context["error"] = error
        return HttpResponse(html_template.render(context, request))

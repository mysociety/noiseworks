from django.forms import TextInput


class SearchWidget(TextInput):
    input_type = "search"
    template_name = "widgets/search.html"

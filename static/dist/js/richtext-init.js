document.addEventListener('DOMContentLoaded', function () {
  if (typeof Quill === 'undefined') return;

  document.querySelectorAll('textarea[data-richtext="true"]').forEach(function (textarea) {
    if (textarea.dataset.richtextInitialized === 'true') return;
    textarea.dataset.richtextInitialized = 'true';

    const wrapper = document.createElement('div');
    wrapper.className = 'richtext-editor-wrapper';

    const editor = document.createElement('div');
    editor.className = 'richtext-editor';
    const rows = parseInt(textarea.getAttribute('rows') || '10', 10);
    editor.style.minHeight = Math.max(rows * 1.5, 12) + 'rem';

    textarea.style.display = 'none';
    textarea.parentNode.insertBefore(wrapper, textarea);
    wrapper.appendChild(editor);
    wrapper.appendChild(textarea);

    const quill = new Quill(editor, {
      theme: 'snow',
      modules: {
        toolbar: [
          [{ header: [3, 4, false] }],
          ['bold', 'italic', 'underline'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'blockquote'],
          ['clean'],
        ],
      },
    });

    if (textarea.value) {
      quill.clipboard.dangerouslyPasteHTML(textarea.value);
    }

    function getHtml() {
      const html = quill.getSemanticHTML ? quill.getSemanticHTML() : quill.root.innerHTML;
      return html === '<p></p>' ? '' : html;
    }

    const form = textarea.closest('form');
    if (form) {
      form.addEventListener('submit', function () {
        textarea.value = getHtml();
      });
    }
  });
});

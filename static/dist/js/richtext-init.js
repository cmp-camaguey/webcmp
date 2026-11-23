document.addEventListener('DOMContentLoaded', function () {
  if (typeof Quill === 'undefined') return;

  document.querySelectorAll('textarea[data-richtext="true"]').forEach(function (textarea) {
    if (textarea.dataset.richtextInitialized === 'true') return;
    textarea.dataset.richtextInitialized = 'true';

    const wrapper = document.createElement('div');
    wrapper.className = 'richtext-editor-wrapper';

    const toolbarRow = document.createElement('div');
    toolbarRow.className = 'd-flex justify-content-end mb-2';
    const previewBtn = document.createElement('button');
    previewBtn.type = 'button';
    previewBtn.className = 'btn btn-sm btn-outline-secondary';
    previewBtn.innerHTML = '<i class="icon ti ti-eye me-1"></i>Vista previa';
    toolbarRow.appendChild(previewBtn);

    const editor = document.createElement('div');
    editor.className = 'richtext-editor';
    const rows = parseInt(textarea.getAttribute('rows') || '10', 10);
    editor.style.minHeight = Math.max(rows * 1.5, 12) + 'rem';

    const preview = document.createElement('div');
    preview.className = 'richtext-content richtext-preview card card-body d-none';
    preview.style.minHeight = editor.style.minHeight;

    textarea.style.display = 'none';
    textarea.parentNode.insertBefore(wrapper, textarea);
    wrapper.appendChild(toolbarRow);
    wrapper.appendChild(editor);
    wrapper.appendChild(preview);
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

    previewBtn.addEventListener('click', function () {
      const showingPreview = !preview.classList.contains('d-none');
      if (showingPreview) {
        preview.classList.add('d-none');
        editor.parentElement.querySelector('.ql-toolbar').classList.remove('d-none');
        editor.classList.remove('d-none');
        previewBtn.innerHTML = '<i class="icon ti ti-eye me-1"></i>Vista previa';
      } else {
        const html = getHtml();
        preview.innerHTML = html || '<p class="text-secondary mb-0">Sin contenido para previsualizar.</p>';
        preview.classList.remove('d-none');
        editor.parentElement.querySelector('.ql-toolbar').classList.add('d-none');
        editor.classList.add('d-none');
        previewBtn.innerHTML = '<i class="icon ti ti-pencil me-1"></i>Editar';
      }
    });

    const form = textarea.closest('form');
    if (form) {
      form.addEventListener('submit', function () {
        textarea.value = getHtml();
      });
    }
  });
});

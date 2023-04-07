import { ViewedEventTracker } from './ViewedEvent';

const completedBlocksKeys = new Set();

export function markBlocksCompletedOnViewIfNeeded(runtime, containerElement) {
  const blockElements = $(containerElement).find(
    '.xblock-student_view[data-mark-completed-on-view-after-delay]',
  ).get();

  if (blockElements.length > 0) {
    const tracker = new ViewedEventTracker();

    const blocksToComplete = [];
    var course_id;

    blockElements.forEach((blockElement) => {
      const markCompletedOnViewAfterDelay = parseInt(
        blockElement.dataset.markCompletedOnViewAfterDelay, 10,
      );
      if (markCompletedOnViewAfterDelay >= 0) {
        tracker.addElement(blockElement, markCompletedOnViewAfterDelay);
      }
      var blockKey = blockElement.dataset.usageId;
      if (blockKey.includes('problem') || blockKey.includes('discussion')) {
        // exclude blocks that are not supposed to be
      } else {
        blocksToComplete.push(blockElement.dataset.usageId);
      }
      course_id = blockElement.dataset.courseId;
    });

    $.ajax({
      type: 'POST',
      url: "/" + course_id + "/batch_completion/",
      data: JSON.stringify({
        blocks: blocksToComplete
      }),
      success: function () {
        $(containerElement).find(
            '.xblock-student_view[data-mark-completed-on-view-after-delay]'
        ).removeAttr('data-mark-completed-on-view-after-delay');
      }
    });
  }
}
